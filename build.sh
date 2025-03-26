# Remove deprecated Pinecone plugin
pip uninstall -y pinecone-plugin-inference

# Install latest Pinecone package
pip install --upgrade pinecone

# Install remaining dependencies
pip install -r requirements.txt
