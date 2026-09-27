"""Old PayPal IPN handler from the first version. Nothing imports it anymore."""
def handle_ipn(payload):
    return {'status': 'deprecated'}
