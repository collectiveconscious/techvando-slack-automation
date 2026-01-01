import os
import asana
from asana.rest import ApiException
import logging

def create_project(project_name, workspace_id):
    """Creates a new project in Asana."""
    access_token = os.environ.get('ASANA_ACCESS_TOKEN')
    if not access_token:
        logging.error("ASANA_ACCESS_TOKEN environment variable not set.")
        return None

    try:
        configuration = asana.Configuration()
        configuration.access_token = access_token
        api_client = asana.ApiClient(configuration)
        
        projects_api = asana.ProjectsApi(api_client)
        
        # Create the project
        body = {
            "data": {
                "name": project_name, 
                "workspace": workspace_id
            }
        }
        
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
