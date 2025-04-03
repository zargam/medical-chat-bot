from flask import Flask, render_template, jsonify, request
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os

app = Flask(__name__)

load_dotenv()

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

embeddings = download_hugging_face_embeddings()
index_name = "mychatbot"

docsearch = PineconeVectorStore.from_existing_index(index_name=index_name, embedding=embeddings)
retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

system_prompt = (
    """You are a helpful medical chatbot. Use your medical knowledge to answer questions accurately and concisely. Follow these instructions:

    1. If the user sends a greeting (e.g., "hi", "hello", "hey"), respond with a friendly greeting.
    2. If the user expresses gratitude (e.g., "thank you", "thanks", "appreciate it"), respond with a polite acknowledgment like "You're welcome!" or "Glad to help!".
    3. If the user sends a farewell (e.g., "bye", "have a nice day", "see you"), respond with a friendly farewell like "Take care!" or "Have a great day!".
    4. If the user asks a medical question (e.g., "What is diabetes?"), use the {context} to provide a clear and concise answer.
    5. If the user asks a follow-up question (e.g., "Tell me in detail", "Explain more"), refer to the chat history to understand the previous medical topic and provide a detailed response based on that, using {context} if available.
    6. If the message is unrelated to the above categories (e.g., "What’s the weather?"), say: "I’m a medical chatbot here to help with health-related questions. How can I assist you with your health today?"
    
    Keep your tone friendly, professional, and supportive. Use the chat history to maintain context only for medical follow-ups."""
)

prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{question}")])

llm = OpenAI(temperature=0.4, max_tokens=500)

rag_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,
    memory=memory,
    combine_docs_chain_kwargs={"prompt": prompt}
)

def detect_intent(message, chat_history):
    history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history])
    intent_prompt = f"""You are an intent classifier. Analyze the following user message in the context of the chat history and classify it into one of these categories:
    - Greeting (e.g., "hi", "hello", "hey", "good morning", "namaste", "hi there! how are you doing today?")
    - Gratitude (e.g., "thank you", "thanks", "appreciate it", "thanks a lot", "thank you so much")
    - Farewell (e.g., "bye", "goodbye", "have a nice day", "see you")
    - Medical Query (e.g., "What is diabetes?", "How to treat fever?")
    - Follow-up (e.g., "Tell me in detail", "Explain more", "What else?")
    - Creator (e.g., "Who developed you?", "Who made you?", "Who created you?")
    - Casual (e.g., "How are you?", "what's going on?", "Nice to meet you", "Good to know")
    - Other (e.g., "What’s the weather?", "Tell me a joke")
    
    Chat History:
    {history_str}
    
    Message: "{message}"
    Return only the category name (e.g., 'Greeting', 'Gratitude', 'Farewell', 'Medical Query', 'Follow-up', 'Creator','Casual','Other'):"""
    
    intent = llm.invoke(intent_prompt).strip()
    print(f"Detected intent for '{message}': {intent}")  # Debugging
    return intent

def clean_response(response):
    # Remove leading/trailing quotes and "System:" prefix if present
    if isinstance(response, str):
        cleaned = response.strip().strip('"').strip("'")
        if cleaned.startswith("System:"):
            cleaned = cleaned[len("System:"):].strip()
        return cleaned
    return response

def handle_message(message):
    # Get current chat history from memory
    chat_history = memory.chat_memory.messages if memory.chat_memory.messages else []
    
    # Detect intent with context
    intent = detect_intent(message, chat_history)
    
    if intent == "Greeting":
        response = "Hi there! How can I assist you with your health today?"  # Direct response
        print(f"Greeting response: {response}")
        memory.save_context({"question": message}, {"answer": response})
        return response
        # greeting_prompt = f"""User said: '{message}'. Respond with a friendly and natural greeting."""
        # response = llm.invoke(greeting_prompt).strip()
        # print(f"Raw Greeting response: {response}")  # Debugging raw output
        # response = clean_response(response)  # Clean quotes
        # if not response:  # Fallback if blank
        #     response = "Hello! How can I assist you today?"
        # print(f"Cleaned Greeting response: {response}")  # Debugging cleaned output
        # memory.save_context({"question": message}, {"answer": response})
        # return response
    
    elif intent == "Gratitude":
        gratitude_prompt = f"""User said: '{message}'. Respond with a polite acknowledgment like 'You're welcome!' or 'Glad to help!'."""
        response = llm.invoke(gratitude_prompt).strip()
        print(f"Raw Gratitude response: {response}")  # Debugging raw output
        response = clean_response(response)  # Clean quotes
        if not response:  # Fallback if blank
            response = "You're welcome! How can I assist you further?"
        print(f"Cleaned Gratitude response: {response}")  # Debugging cleaned output
        memory.save_context({"question": message}, {"answer": response})
        return response
    
    elif intent == "Farewell":
        farewell_prompt = f"""User said: '{message}'. Respond with a friendly farewell like 'Take care!' or 'Have a great day!'."""
        response = llm.invoke(farewell_prompt).strip()
        print(f"Raw Farewell response: {response}")  # Debugging raw output
        response = clean_response(response)  # Clean quotes
        if not response:  # Fallback if blank
            response = "Take care! Feel free to return if you have more questions."
        print(f"Cleaned Farewell response: {response}")  # Debugging cleaned output
        memory.save_context({"question": message}, {"answer": response})
        return response
    
    elif intent == "Medical Query":
        response = rag_chain.invoke({"question": message})
        print(f"Medical Query response: {response['answer']}")  # Debugging
        response["answer"]
        return clean_response(response["answer"])  # Clean quotes
    
    elif intent == "Follow-up":
        last_medical_query = None
        for i in range(len(chat_history) - 1, -1, -1):
            if detect_intent(chat_history[i].content, chat_history[:i]) == "Medical Query":
                last_medical_query = chat_history[i].content
                break
        
        if last_medical_query:
            detailed_prompt = f"""Based on the previous question '{last_medical_query}', the user now asks: '{message}'. Provide a detailed response using the medical data from the Pinecone database."""
            response = rag_chain.invoke({"question": detailed_prompt})
            print(f"Follow-up response: {response['answer']}")  # Debugging
            return clean_response(response["answer"])  # Clean quotes
        else:
            response = "I don’t have enough context to provide details. Could you please ask a medical question first?"
            memory.save_context({"question": message}, {"answer": response})
            return response
        
    elif intent == "Creator":
        response = "Zargam Hussain"  # Direct response without LLM generation
        memory.save_context({"question": message}, {"answer": response})
        return response
    
    elif intent == "Casual":
        casual_prompt = f"""You are a friendly medical chatbot. The user said: '{message}'. Respond in a casual, conversational tone in English while keeping it relevant to your role as a medical assistant. Keep the response short and end with a question to keep the chat going. Examples:
        - User: "How are you?" → "I’m doing great, thanks! How can I help you with your health today?"
        - User: "What’s up?" → "Just chilling, ready to help! What’s on your mind today?"
        - User: "Nice to meet you" → "Nice to meet you too! How can I assist you today?"
        """
        response = llm.invoke(casual_prompt).strip()
        print(f"Raw Casual response: {response}")
        response = clean_response(response)
        if not response:
            response = "Good to chat with you! How can I support your health today?"  # Fallback
        print(f"Cleaned Casual response: {response}")
        memory.save_context({"question": message}, {"answer": response})
        return response
    else:
        response = "I’m a medical chatbot here to help with health-related questions. How can I assist you with your health today?"
        print(f"Other response: {response}")  # Debugging
        memory.save_context({"question": message}, {"answer": response})
        return response

@app.route("/")
def index():
    return render_template('chat.html')

@app.route("/get", methods=["GET", "POST"])
def chat():
    msg = request.form["msg"]
    response = handle_message(msg)
    if not response:  # Final fallback for blank response
        response = "Sorry, I couldn’t process that. How can I assist you?"
    return str(response)
    

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
