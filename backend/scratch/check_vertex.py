import vertexai.generative_models as gm
try:
    print(f"SafetySetting: {gm.SafetySetting}")
except AttributeError:
    print("SafetySetting not found in vertexai.generative_models")

from vertexai.generative_models import SafetySetting
print("Imported successfully")
