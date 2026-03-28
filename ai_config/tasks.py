from celery import shared_task


@shared_task(name='ai_config.ai_reply', bind=True, max_retries=2, default_retry_delay=5)
def ai_reply_task(self, customer_id: str):
    """
    Celery task that runs AIReplyService in a worker process.
    Active when AI_ASYNC_BACKEND = 'celery' in settings.

    To enable:
      1. pip install celery[redis]
      2. Create backend/main/celery.py and update main/__init__.py
      3. Set CELERY_BROKER_URL and AI_ASYNC_BACKEND=celery in .env
      4. Start worker: celery -A main worker -l info
    """
    from conversations.ai_service import AIReplyService
    try:
        AIReplyService._run(customer_id)
    except Exception as exc:
        raise self.retry(exc=exc)
