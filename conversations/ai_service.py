import logging
import threading
from django.conf import settings

logger = logging.getLogger(__name__)


class AIReplyService:
    """
    Decides whether to auto-reply, builds context, calls the AI provider,
    and sends the reply via ReplyService.

    Customer-level AI toggle (customer.ai_enabled):
      None  = follow business AIConfig.enabled
      True  = always reply for this customer (override on)
      False = never reply for this customer (opt-out)

    Dispatch backend (AI_ASYNC_BACKEND setting):
      'thread' — fire-and-forget daemon thread (default, works on Render free)
      'celery' — delegate to Celery task (when a worker is available)
    """

    # ── Public entry point ────────────────────────────────────────────────────

    @staticmethod
    def dispatch(customer):
        """
        Called after every inbound customer message.
        Runs the AI reply in the background so it never blocks the webhook response.
        """
        backend = getattr(settings, 'AI_ASYNC_BACKEND', 'thread')

        if backend == 'celery':
            from ai_config.tasks import ai_reply_task
            ai_reply_task.delay(str(customer.id))
        else:
            t = threading.Thread(
                target=AIReplyService._run,
                args=(str(customer.id),),
                daemon=True,
            )
            t.start()

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _run(customer_id: str):
        """Execute in a background thread (or called directly by a Celery task)."""
        from .models import Customer, Message

        try:
            customer = Customer.objects.select_related(
                'business', 'last_channel__channel_type'
            ).get(id=customer_id)
        except Customer.DoesNotExist:
            logger.warning('AIReplyService: customer %s not found', customer_id)
            return

        if not AIReplyService._should_reply(customer):
            return

        try:
            ai_config, system_prompt, messages = AIReplyService._build_context(customer)
        except Exception:
            logger.exception('AIReplyService: failed to build context for customer %s', customer_id)
            return

        if not messages:
            return

        try:
            from integrations.ai_providers.factory import get_ai_provider
            provider = get_ai_provider(ai_config)
            reply_text = provider.complete(system_prompt, messages)
        except Exception:
            logger.exception('AIReplyService: provider error for customer %s', customer_id)
            return

        if not reply_text:
            return

        try:
            from .services import ReplyService
            message = ReplyService.send(
                customer=customer,
                content=reply_text,
                speaker=Message.Speaker.BOT,
            )
            AIReplyService._broadcast(customer, message)
        except Exception:
            logger.exception('AIReplyService: failed to send reply for customer %s', customer_id)

    @staticmethod
    def _should_reply(customer) -> bool:
        """
        Evaluate whether the AI should auto-reply.

          customer.ai_enabled=False → hard opt-out, skip regardless of business setting
          customer.ai_enabled=True  → hard opt-in, reply if business has valid config
          customer.ai_enabled=None  → inherit business AIConfig.enabled
        """
        from ai_config.models import AIConfig

        # Hard opt-out at customer level
        if customer.ai_enabled is False:
            return False

        try:
            config = AIConfig.objects.get(business=customer.business)
        except AIConfig.DoesNotExist:
            return False

        if not config.api_key:
            return False

        # Hard opt-in at customer level — business config must still have a key
        if customer.ai_enabled is True:
            return True

        # customer.ai_enabled is None — follow business setting
        return config.enabled

    @staticmethod
    def _build_context(customer):
        """
        Returns (ai_config, system_prompt, messages).

        system_prompt = business system_prompt + live customer info block.
        messages      = [{'role': 'user'|'model', 'content': '...'}]
        'model' role covers both agent and previous bot replies.
        """
        from ai_config.models import AIConfig
        from .models import Message

        config = AIConfig.objects.get(business=customer.business)

        # Append known customer details so the AI can personalise its replies
        info_lines = []
        if customer.name:
            info_lines.append(f'Name: {customer.name}')
        if customer.phone:
            info_lines.append(f'Phone: {customer.phone}')
        if customer.email:
            info_lines.append(f'Email: {customer.email}')

        system_prompt = config.system_prompt or ''
        if info_lines:
            customer_block = 'Current customer:\n' + '\n'.join(info_lines)
            system_prompt = f'{system_prompt}\n\n{customer_block}' if system_prompt else customer_block

        recent = list(
            Message.objects.filter(customer=customer)
            .order_by('-timestamp')[:config.context_messages]
        )
        recent.reverse()  # chronological order for the prompt

        messages = [
            {
                'role': 'user' if msg.speaker == Message.Speaker.CUSTOMER else 'model',
                'content': msg.content,
            }
            for msg in recent
            if msg.content.strip()
        ]

        return config, system_prompt, messages

    @staticmethod
    def _broadcast(customer, message):
        """Push the bot reply to agents via WebSocket (chat window + inbox sidebar)."""
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        payload = {
            'id': str(message.id),
            'speaker': message.speaker,
            'speaker_agent': None,
            'channel_type': message.channel_type,
            'content_type': message.content_type,
            'content': message.content,
            'attachments': message.attachments,
            'is_read': message.is_read,
            'send_error': message.send_error or None,
            'timestamp': message.timestamp.isoformat(),
        }

        async_to_sync(channel_layer.group_send)(
            f'customer_{customer.id}',
            {'type': 'chat.message', 'message': payload},
        )
        async_to_sync(channel_layer.group_send)(
            f'inbox_{customer.business_id}',
            {'type': 'inbox.update', 'customer_id': str(customer.id), 'message': payload},
        )
