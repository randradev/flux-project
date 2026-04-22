from google.cloud import aiplatform

def list_models():
    aiplatform.init(project="flux-493520", location="us-central1")
    model_list = aiplatform.Model.list()
    for model in model_list:
        print(f"Model ID: {model.display_name}, Resource Name: {model.resource_name}")

if __name__ == "__main__":
    try:
        list_models()
    except Exception as e:
        print(f"Error listing models: {e}")
