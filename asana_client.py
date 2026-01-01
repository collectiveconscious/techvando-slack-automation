import os
import asana
import logging

def create_project(project_name, workspace_id):
    """Creates a new project in Asana."""
    access_token = os.environ.get('ASANA_ACCESS_TOKEN')
    if not access_token:
        logging.error("ASANA_ACCESS_TOKEN environment variable not set.")
        return None

    try:
        client = asana.Client.access_token(access_token)
        
        # Create the project
        result = client.projects.create_project({
            'name': project_name, 
            'workspace': workspace_id
        })
        
        logging.info(f"Asana project '{project_name}' created with GID: {result['gid']}")
        return result['gid']
    except Exception as e:
        logging.error(f"Error creating Asana project: {e}")
        return None
