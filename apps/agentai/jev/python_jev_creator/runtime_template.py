def _python_jev_creator_decide(original, state, question):
    """Noul decision with original-condition fallback; no SDK dependency."""
    import json
    import math
    import os
    import urllib.request
    import warnings

    fallback = bool(original)
    key = os.environ.get('TYPESAFE_API_KEY')
    if not key or os.environ.get('JEV_ENABLED', '1') == '0':
        return fallback
    # Send only explicitly named primitive variables, never locals()/globals().
    if not all(type(value) in (str, int, float, bool, type(None)) for value in state.values()):
        return fallback
    try:
        payload = json.dumps({
            'model': os.environ.get('JEV_MODEL', 'jev-latest'),
            'state': state,
            'questions': {'decision': {'type': 'noul', 'instructions': question}},
        }, allow_nan=False).encode('utf-8')
        request = urllib.request.Request('https://api.typesafe.ai/v1/systemone',
            data=payload, headers={'Authorization': 'Bearer ' + key,
                                   'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=10) as response:
            answer = json.load(response)['answers']['decision']
        probability = answer['noul']
        if answer.get('type') != 'noul' or type(probability) not in (int, float):
            raise ValueError('Invalid Noul response')
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('Invalid Noul probability')
        if probability >= 0.8:
            return True
        if probability <= 0.2:
            return False
    except Exception:
        warnings.warn('Jev request failed; using original condition.', RuntimeWarning)
    return fallback
