**Project Title: AI-Powered Travel Concierge Web Application**

**Demo:** [Watch the demo video](https://drive.google.com/file/d/1A3sk1zfgQqURGWCWnvSdO1psyn23eMFL/view?usp=drive_link)

*Overview/Goal:*

Developed a web application using Streamlit and FastAPI that interacts with an AI agent (Google's ADK 'Travel Concierge,' deployed on Vertex AI as a Reasoning Engine) to help users plan trips, get suggestions, and save itineraries. Key features include multi-turn conversation, itinerary generation, saving/viewing trips, Firestore integration.

*Bullet list of main functionalities:*

- Interactive chat with the Travel Concierge AI.

- Multi-turn conversational capabilities with context retention.

- Generation of structured travel itineraries.

- Saving generated itineraries to a Firestore database.

- Viewing lists of upcoming/past saved trips.

*Technologies Used:*

- Frontend: Streamlit

- Backend: FastAPI (Python)

- AI Agent: Google Agent Development Kit (ADK), Gemini models (e.g., Gemini Flash), deployed on Google Cloud Vertex AI (Reasoning Engines). 

- Agent Code: agents/travel-concierge/travel_concierge

- Database: Google Cloud Firestore

- Cloud Platform: Google Cloud Platform (GCP)

- Key Python Libraries: google-cloud-aiplatform, google-cloud-firestore, requests, pydantic, python-dotenv, uvicorn.

*Architecture:*

Simple diagram showing the components: Streamlit UI -> FastAPI Backend -> Vertex AI Agent -> Firestore.

*Setup and Installation:*

- Prerequisites (Python version, Google Cloud SDK installed and configured, gcloud auth application-default login executed).

- Running the Application:

  - Command to start the FastAPI backend (e.g., uvicorn main:app --reload from the backend directory).

  - Command to start the Streamlit frontend (e.g., streamlit run webapp.py from the webapp directory).

*Key Learnings / Skills Demonstrated:*

- AI Agent Interaction & Integration (Vertex AI SDK, Reasoning Engines).

- Full-Stack Web Development (Python, FastAPI, Streamlit).

- API Design (RESTful API with FastAPI).

- Cloud Services (GCP, Vertex AI, Firestore).

- Database Integration (NoSQL with Firestore).

- Session Management for Conversational AI.

- Pydantic for data validation and serialization.

- Debugging and problem-solving in a multi-component system.

