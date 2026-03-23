from google.cloud import firestore
from app.core.config import settings

# Uses Application Default Credentials locally (gcloud auth application-default login).
# In Cloud Run, uses the service account attached to the revision automatically.
db = firestore.Client(project=settings.gcp_project, database=settings.firestore_db)
