
from accounts.models import Business

def handle_demo_prerequisite(data):
    """
    Handle any prerequisites for demo sessions, such as validating the demo_auth_key.
    This is a placeholder function and should be implemented with actual logic as needed.
    """
    # Example: Validate the demo_auth_key against a known value or database record
    valid_demo_keys = ["ChatBridgeDemo"]  # This should come from a secure source
    if data['demo_auth_key'] not in valid_demo_keys:
        raise ValueError("Invalid demo authentication key.")
    
    demo_business_id = '79bd4bb9-cdbe-4bc0-972d-a42c189c7a6f'
    bs_name = data.get('bussiness_name', 'Demo Business')
    
    business = Business.objects.filter(id=demo_business_id).first()
    if not business:
        raise ValueError("Demo business not found.")
        # business = Business.objects.create(name=bs_name)

    business.name = bs_name
    business.save(update_fields=['name'])

    ai_config = data.get('ai_config')

    if ai_config:
        from ai_config.models import AIConfig

        AIConfig.objects.update_or_create(
            business=business,
            defaults={
                'enabled': ai_config.get('enabled', False),
                'provider': ai_config.get('provider', AIConfig.Provider.GEMINI),
                'api_key': ai_config.get('api_key', ''),
                'model_name': ai_config.get('model_name', 'gemini-2.0-flash'),
                'system_prompt': ai_config.get('system_prompt', ''),
                'context_messages': ai_config.get('context_messages', 10),
            }
        )

    