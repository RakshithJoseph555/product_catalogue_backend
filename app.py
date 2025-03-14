

from flask import Flask, request, jsonify
from pymongo import MongoClient
from azure.storage.blob import BlobServiceClient,generate_blob_sas, BlobSasPermissions
from werkzeug.utils import secure_filename
from flask_cors import CORS
from bson import ObjectId
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import re
load_dotenv()
app = Flask(__name__)
CORS(app)

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("CONTAINER_NAME")
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME")
ACCOUNT_KEY=os.getenv("ACCOUNT_KEY")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["product_db"]
collection = db["products"]

def generate_blob_sas_url(blob_name):
    sas_token=generate_blob_sas(
        account_name=ACCOUNT_NAME,
        container_name=CONTAINER_NAME,
        blob_name=blob_name,
        account_key=ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )
    return f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}?{sas_token}"

# Helper Function: Upload Image to Azure Blob Storage
def upload_to_azure_blob(image):
    """Uploads an image to Azure Blob Storage and returns its URL."""
    filename = secure_filename(image.filename)
    
    try:
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=filename)
        blob_client.upload_blob(image, overwrite=True)
        return generate_blob_sas_url(filename)

    except Exception as e:
        print("Azure Blob Upload Error:", str(e))
        return None

# Add a Product
@app.route("/add_product", methods=["POST"])
def add_product():
    name = request.form.get("name")
    price = float(request.form.get("price", 0))
    category = request.form.get("category")
    
    image_url = None
    if "image" in request.files:
        image = request.files["image"]
        print("add")
        print(image)
        image_url = upload_to_azure_blob(image)

    product = {
        "name": name,
        "price": price,
        "category": category,
        "imageUrl": image_url
    }

    product_id = collection.insert_one(product).inserted_id
    return jsonify({"message": "Product added", "product_id": str(product_id), "imageUrl": image_url}), 201

# # List All Products
# @app.route('/list_products', methods=['GET'])
# def list_products():
#     products = list(collection.find({}))
#     for product in products:
#         product["_id"] = str(product["_id"])
#     return jsonify(products), 200

def extract_blob_name(image_url):
    """Extract blob filename from the previously stored URL."""
    match = re.search(r"/([^/]+)\?", image_url)  # Extract filename between last '/' and '?'
    return match.group(1) if match else None

@app.route('/list_products', methods=['GET'])
def list_products():
    products = list(collection.find({}))
    
    for product in products:
        product["_id"] = str(product["_id"])
        
        # Extract blob filename from the old URL and generate a new one
        if "image_url" in product:
            blob_name = extract_blob_name(product["image_url"])
            if blob_name:
                product["image_url"] = generate_blob_sas_url(blob_name)

    return jsonify(products), 200

# Update a Product
@app.route('/update_product/<product_id>', methods=['PUT'])
def update_product(product_id):
    # data = request.json
    # if "_id" in data:
    #     data.pop("_id")
    # def update_product(product_id):
    data = request.json
    if "_id" in data:
        data.pop("_id")
    result = collection.update_one({"_id": ObjectId(product_id)}, {"$set": data})
    
    if result.matched_count == 0:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"message": "Product updated"}), 200

# Delete a Product
@app.route('/delete_product/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    result = collection.delete_one({"_id": ObjectId(product_id)})
    
    if result.deleted_count == 0:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"message": "Product deleted"}), 200

# Clear All Products
@app.route('/clear_products', methods=['DELETE'])
def clear_products():
    collection.delete_many({})
    return jsonify({"message": "All products deleted"}), 200


# @app.route('/image_url', methods=['GET'])
# def image_url():
#     image_url=None
#     if "image" in request.files:
#         image = request.files["image"]
#         image_url = upload_to_azure_blob(image)
#     return jsonify({"image_url": image_url}), 200


@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image = request.files['image']
    print("upload")
    print(image)
    try:
        image_url=upload_to_azure_blob(image)
        return jsonify({"image_url": image_url}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
