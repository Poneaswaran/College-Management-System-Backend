"""
Custom multipart request handler for Strawberry GraphQL
"""
import json
from typing import Any, Dict
from django.http import HttpRequest


def parse_multipart_graphql_request(request: HttpRequest) -> Dict[str, Any]:
    """
    Parse GraphQL multipart request according to the spec:
    https://github.com/jaydenseric/graphql-multipart-request-spec
    
    Expected format:
    - operations: JSON string with query and variables
    - map: JSON string mapping file keys to variable paths  
    - files: uploaded files with keys matching the map
    
    Returns:
    Dict with 'query', 'variables', 'operationName' keys
    """
    try:
        # Get operations from POST data
        operations_str = request.POST.get('operations')
        if not operations_str:
            raise ValueError("Missing 'operations' field in multipart request")
        
        operations = json.loads(operations_str)
        
        # Get file mapping
        map_str = request.POST.get('map')
        if map_str:
            files_map = json.loads(map_str)
            
            # Map files to variables
            for file_key, paths in files_map.items():
                uploaded_file = request.FILES.get(file_key)
                if uploaded_file:
                    for path in paths:
                        _set_nested_value(operations, path, uploaded_file)
        
        return operations
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in multipart request: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error parsing multipart request: {str(e)}")


def _set_nested_value(data: Dict[str, Any], path: str, value: Any) -> None:
    """
    Set a value in a nested dictionary using dot notation path.
    
    Example: path="variables.profilePicture" will set data['variables']['profilePicture'] = value
    """
    keys = path.split('.')
    current = data
    
    # Navigate to the parent of the target key
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    # Set the value
    current[keys[-1]] = value
