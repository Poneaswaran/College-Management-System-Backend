import hashlib
import json
from django.core.serializers.json import DjangoJSONEncoder

def generate_etag(data):
    """
    Generate an entity tag (ETag) for the given data.
    The data can be a dictionary, list, or any JSON-serializable object.
    """
    if data is None:
        return None
    
    # Serialize data to a consistent JSON string
    # Using DjangoJSONEncoder to handle datetime objects
    serialized_data = json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)
    
    # Create an MD5 hash of the serialized data
    return hashlib.md5(serialized_data.encode('utf-8')).hexdigest()

def check_etag(request, etag):
    """
    Check if the ETag in the request matches the generated ETag.
    """
    if not etag:
        return False
        
    if_none_match = request.META.get('HTTP_IF_NONE_MATCH')
    if if_none_match and if_none_match.strip('"') == etag:
        return True
        
    return False
