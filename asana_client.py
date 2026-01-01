import os
import asana
from asana.rest import ApiException
import logging

def _clean_asana_id(asana_id):
    """Extracts the numeric ID from an Asana URL or returns the ID itself."""
    if not asana_id:
        return None
    
    clean_id = str(asana_id)
    if clean_id.startswith("http"):
         # Remove trailing slash if present
         clean_id = clean_id.rstrip("/")
         # Get last part
         clean_id = clean_id.split("/")[-1]
    
    # Ensure it is now just digits (log warning if not, but return it anyway)
    if not clean_id.isdigit():
        logging.warning(f"Asana ID '{clean_id}' does not look like a numeric ID. Attempting to use it anyway.")
        
    return clean_id

def create_project(project_name, workspace_id, team_id=None):
    """Creates a new project in Asana."""
    access_token = os.environ.get('ASANA_ACCESS_TOKEN')
    if not access_token:
        logging.error("ASANA_ACCESS_TOKEN environment variable not set.")
        return None

    workspace_id = _clean_asana_id(workspace_id)
    team_id = _clean_asana_id(team_id)

    try:
        configuration = asana.Configuration()
        configuration.access_token = access_token
        api_client = asana.ApiClient(configuration)
        
        projects_api = asana.ProjectsApi(api_client)
        
        # Create the project
        data_payload = {
            "name": project_name
        }
        
        if team_id:
            data_payload["team"] = team_id
        else:
            data_payload["workspace"] = workspace_id
            
        body = {"data": data_payload}
        
        logging.info(f"Creating Asana project with body: {body}")
        
        result = projects_api.create_project(body, opts={})
        
        # In v5, result is an object, usually with a 'data' attribute or accessed directly depending on return type
        # Typically result.data.gid
        gid = result.data.gid
        
        logging.info(f"Asana project '{project_name}' created with GID: {gid}")
        return gid
    except ApiException as e:
        logging.error(f"Error creating Asana project: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error creating Asana project: {e}")
        return None
