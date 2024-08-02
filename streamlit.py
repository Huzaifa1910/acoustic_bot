import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os
import pandas as pd
import time

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPEN_AI"))

# Function to get the assistant
def get_assistant():
    # df = pd.read_csv('Acoustic_Panel_Descriptions_New.csv')
    df = pd.read_csv('Panel Desc - Sheet1 (1).csv')
    assistants = client.beta.assistants.list().to_dict()
    vectors = client.beta.vector_stores.list().to_dict()

    if len(assistants['data']) == 0:
        assistant = client.beta.assistants.create(
            name="Acoustic Panel Assistant",
            # instructions=f"Behave like a consultant to make the user able to buy best Acoustic Panel as per the need. Use your knowledge base to ask the question about his needs of acoustic panel, must ask questions from all of the stages, do not ask anything out of the document and don't suggest anything outside of the data, and suggest the best suited top 3 panels.ask each question one by one suggest names and short description of best recommended panels from the data {df} also ask any relevant question if needed. Start Suggesting Panels after stage 5 but keep asking other stage question to make results more accurate",
            instructions=f"""Your task is to assist the user in selecting the best acoustic panel based on their specific requirements. The conversation should be interactive, guided by a series of questions across nine stages.
                At the end of the conversation, recommend the top 3 acoustic panels based on the user's responses along with the Link, use the data for recommendation {df}.
                The stages are: Type, Pattern, Attributes, Resonating Boards, Application, Acoustic Performance, Aesthetic Preferences, Speaker Configuration, and Acoustic Door Preference. but do not use stage names in any of the question neither stage number question for each stage, What type of acoustic panel are you looking for: Custom Panels or Standard Panels?,  Do you prefer acoustic panels with a specific pattern, such as Tiles, Wood Grid, or Modular, or do you prefer panels without a specific pattern?, Would you like the panel to have any specific attributes, such as Curved Edges, Straight Edges, Square, Rectangular, or any other feature you have in mind?, Are you looking for panels with tuned resonating boards?, Where do you plan to use the acoustic panels? Would it be for a studio, office, home theater, or another specific location? (In Stage 6, this question should only appear IF the user is doing a music related room. If an office or home office si being done (not related to music directly), that question is not needed), Are the panels intended for a specific room type (e.g., recording room, mixing room)? Are you looking for broadband absorption panels? Do you prefer a sound profile that is bass-heavy, balanced, or enhanced for clarity?, Are you looking for panels with a modern look, a classic design, or ones that blend with your existing room decor?.  Do you intend to use this room for Dolby Atmos or surround sound? If yes, what surround configuration do you plan to use (e.g., 5.1.4, 7.1.4, 9.1.4, 11.4)? Also, what kind of speakers do you intend to use?, Do you wish to add an acoustic door to the design, so that no sound leaks outside the space? ask above questions one by one, and complete all nine stages
                Remember and reference their responses to ensure a cohesive conversation. 
                Once all stages are complete. Provide a short description for each recommended panel, explaining why they are a good fit. 
                Follow these guidelines to ensure a smooth and helpful interaction that leads to the best possible recommendation for the user.
                If the user is not sure for the answer, the explain the question and ask again you can not move on to the next stage without getting a perfect answer from user. 
                If the user already given some information that is satisfying any other stage, you must skip that stage and move to the next stage.
                Also if the user is using panels for music room then ask question that is about specific room type mixing room one.
                Do not mention stage name and number in question. """,
            model="gpt-3.5-turbo",
            tools=[{"type": "file_search"}],
        )
        vector_store = client.beta.vector_stores.create(name="Acoustic Panels")
        file_paths = ["Question - Stages for ChatBot.pdf"]
        file_streams = [open(path, "rb") for path in file_paths]
        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=file_streams
        )
        assistant = client.beta.assistants.update(
            assistant_id=assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )
    else:
        assistant = client.beta.assistants.retrieve(assistants['data'][0]['id'])
        vector_store = client.beta.vector_stores.retrieve(vectors['data'][0]['id'])
        assistant = client.beta.assistants.update(
            assistant_id=assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )

    return assistant

# Function to create a new thread
def first_thread():
    thread = client.beta.threads.create()
    return thread

# Function to load an existing thread
def load_thread(thread_id):
    thread = client.beta.threads.retrieve(thread_id)
    return thread

# Streamlit app layout
st.title("Acoustic Panel Consultant")

if 'assistant' not in st.session_state:
    st.session_state.assistant = get_assistant()

if 'thread' not in st.session_state:
    st.session_state.thread = first_thread()

# User input


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# Function to handle chat input and response
def handle_chat_input(prompt):
    thread = load_thread(st.session_state.thread.id)
    
    # Create a new message in the thread
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt,
    )
    
    # Run the assistant
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id, assistant_id=st.session_state.assistant.id
    )
    
    # Get the response
    messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
    message_content = messages[0].content[0].text
    annotations = message_content.annotations
    citations = []
    for index, annotation in enumerate(annotations):
        message_content.value = message_content.value.replace(annotation.text, f"[{index}]")
        if file_citation := getattr(annotation, "file_citation", None):
            cited_file = client.files.retrieve(file_citation.file_id)
            citations.append(f"[{index}] {cited_file.filename}")

    return message_content.value, citations

# UI for chat input and display
def chat_ui():
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # Get assistant response
        response, citations = handle_chat_input("Suggest me best acoustic panels.")
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Display assistant response in chat message container
    # with st.chat_message("assistant"):
    #     st.markdown(response)
    # Add assistant response to chat history
    # st.subheader("Ask your questions below:")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Type your question..."):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Get assistant response
        response, citations = handle_chat_input(prompt)
        
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})


# Set up UI
chat_ui()
