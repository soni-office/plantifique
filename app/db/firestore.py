from google.cloud import firestore

# Firestore client — uses Application Default Credentials (gcloud auth application-default login)
# No JSON key file needed locally since we ran `gcloud auth application-default login`
db = firestore.Client(project="tiktok-ai-agent-488417", database="plantifique-pop-dev")
