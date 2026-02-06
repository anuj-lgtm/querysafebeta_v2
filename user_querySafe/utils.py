def get_registration_redirect(user):
    """Determine where to redirect user based on registration status"""
    if user.registration_status == 'registered':
        return 'verify_otp', 'Please verify your email first.'
    return None, None