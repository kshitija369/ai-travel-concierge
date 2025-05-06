"""Main module for the FastAPI application."""

from typing import Any, Dict, List, Optional
import uuid
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

try:
  # Use relative imports if these files are in the same 'app' package
  from . import vertex_ai_client
  from .vertex_ai_client import initialize_globals_and_agent, process_agent_query
  print("Successfully imported from .vertex_ai_client (main.py).")
except ImportError:
  print(f"ERROR (main.py): Could not import from vertex_ai_client.py: {e}.")
  vertex_ai_client = None
  def initialize_globals_and_agent(): return False
  def process_agent_query(user_query: str, session_id: Optional[str], user_id: str) -> Dict[str, Any]:
    return {"session_id": session_id, "display_text": "Agent client module not loaded.",
            "error_message": "Agent client module not loaded.", "structured_itinerary_raw": None}

try:
  from . import db # Import the db module
  from .db import ( # Import specific names from db.py
    initialize_firestore_client, save_trip_to_firestore,
    get_trips_for_user_from_firestore, get_trip_details_from_firestore,
    Itinerary, AirportEvent, AttractionEvent, FlightEvent, HotelEvent, ItineraryDay # Pydantic models
  )
  print("Successfully imported from .db (main.py).")
  db_available = True
except ImportError:
  db_available = False
  class Itinerary(BaseModel): pass # Dummy

# --- Pydantic Models for API Endpoints ---
class UserInput(BaseModel):
  query: str
  session_id: Optional[str] = None

class AgentResponse(BaseModel):
  session_id: str
  display_text: str
  suggestions: Optional[List[str]] = None
  structured_itinerary: Optional[Itinerary] = None # Uses Itinerary from db.py
  active_sub_agents: Optional[List[str]] = None
  requires_follow_up: bool = True
  error_message: Optional[str] = None

class SaveTripRequest(BaseModel):
  client_session_id: str
  itinerary_data: Itinerary # Uses Itinerary from db.py

class TripSummary(BaseModel):
  trip_id: str
  trip_name: str
  start_date: Optional[str] = None
  end_date: Optional[str] = None
  status: Optional[str] = None

app = FastAPI()
_fastapi_agent_service_initialized = False
_firestore_client_initialized = False
_sdk_session_id_cache: Dict[str, str] = {} # In-memory cache for SDK session IDs

@app.on_event("startup")
async def startup_event():
  global _fastapi_agent_service_initialized, _firestore_client_initialized, _sdk_session_id_cache
  _sdk_session_id_cache.clear()
  print("INFO (main.py): FastAPI app starting up...")
  if vertex_ai_client and initialize_globals_and_agent():
    _fastapi_agent_service_initialized = True
    print(f"INFO (main.py): Vertex AI Engine initialized status (from client module): {vertex_ai_client.IS_INITIALIZED}")
  else:
    _fastapi_agent_service_initialized = False
    logging.critical("CRITICAL (main.py): Vertex AI Agent Engine FAILED to initialize.")

  if db_available and initialize_firestore_client(database_id="ai-agent-dev"): # Pass your DB ID
    _firestore_client_initialized = True
    print("INFO (main.py): Firestore client initialized successfully.")
  else:
    _firestore_client_initialized = False
    logging.critical("CRITICAL (main.py): Firestore client FAILED to initialize.")

  print(f"INFO (main.py): FastAPI local _fastapi_agent_service_initialized: {_fastapi_agent_service_initialized}")
  print(f"INFO (main.py): FastAPI local _firestore_client_initialized: {_firestore_client_initialized}")

@app.post("/chat", response_model=AgentResponse)
async def chat_with_agent_endpoint(user_input: UserInput):
  global _fastapi_agent_service_initialized, _sdk_session_id_cache

  if not _fastapi_agent_service_initialized:
    raise HTTPException(status_code=503, detail="Agent service not available.")
  if not (vertex_ai_client and vertex_ai_client.IS_INITIALIZED and vertex_ai_client.REMOTE_AGENT_ENGINE):
    raise HTTPException(status_code=503, detail="Agent engine component missing.")

  client_managed_session_id = user_input.session_id or str(uuid.uuid4())
  stable_agent_user_id = f"web_user_{client_managed_session_id}"

  print(f"FASTAPI DEBUG (main.py): UserInput: query='{user_input.query[:50]}...', client_managed_session_id='{client_managed_session_id}'")
  print(f"FASTAPI DEBUG (main.py): Derived stable_agent_user_id: {stable_agent_user_id}")

  sdk_session_id_for_agent_query = _sdk_session_id_cache.get(stable_agent_user_id)

  if not sdk_session_id_for_agent_query:
    print(f"FASTAPI DEBUG (main.py): No cached SDK session ID for {stable_agent_user_id}. Calling create_session.")
    if hasattr(vertex_ai_client.REMOTE_AGENT_ENGINE, 'create_session'):
      try:
        session_info = vertex_ai_client.REMOTE_AGENT_ENGINE.create_session(user_id=stable_agent_user_id)
        returned_sdk_id = None
        if isinstance(session_info, dict): returned_sdk_id = session_info.get("id")
        elif hasattr(session_info, 'id'): returned_sdk_id = session_info.id
        if returned_sdk_id:
          sdk_session_id_for_agent_query = returned_sdk_id
          _sdk_session_id_cache[stable_agent_user_id] = sdk_session_id_for_agent_query
          print(f"FASTAPI DEBUG (main.py): SDK create_session returned AND CACHED sdk_session_id: {sdk_session_id_for_agent_query} for {stable_agent_user_id}.")
        else:
          sdk_session_id_for_agent_query = client_managed_session_id
          _sdk_session_id_cache[stable_agent_user_id] = sdk_session_id_for_agent_query
          print(f"FASTAPI WARN (main.py): SDK create_session no ID. Using and caching client_managed_id '{client_managed_session_id}'.")
      except Exception as cs_e:
        sdk_session_id_for_agent_query = client_managed_session_id
        _sdk_session_id_cache[stable_agent_user_id] = sdk_session_id_for_agent_query
        print(f"FASTAPI WARN (main.py): Error SDK create_session for {stable_agent_user_id}: {cs_e}. Using and caching '{client_managed_session_id}'.")
    else:
      sdk_session_id_for_agent_query = client_managed_session_id
      _sdk_session_id_cache[stable_agent_user_id] = sdk_session_id_for_agent_query
      print(f"FASTAPI DEBUG (main.py): No 'create_session'. Using and caching client_managed_id.")
  else:
    print(f"FASTAPI DEBUG (main.py): Reusing CACHED sdk_session_id: {sdk_session_id_for_agent_query} for {stable_agent_user_id}.")

  agent_dict_response = process_agent_query(
      user_query=user_input.query,
      session_id=sdk_session_id_for_agent_query,
      user_id=stable_agent_user_id
  )

  parsed_itinerary: Optional[Itinerary] = None
  raw_itinerary_data = agent_dict_response.get("structured_itinerary_raw")
  if raw_itinerary_data and isinstance(raw_itinerary_data, dict) and db_available:
    try:
      # Using Pydantic V2 model_validate, fallback to V1 ** unpacking
      parsed_itinerary = Itinerary.model_validate(raw_itinerary_data)
    except AttributeError: # If model_validate doesn't exist (Pydantic V1)
      parsed_itinerary = Itinerary(**raw_itinerary_data)
    except ValidationError as ve:
      logging.error(f"ERROR (main.py): Itinerary parsing (ValidationError) for {client_managed_session_id}: {ve}.")
      parsed_itinerary = None
    except Exception as e:
      logging.exception(f"ERROR (main.py): Itinerary parsing (Other) for {client_managed_session_id}: {e}.")
      parsed_itinerary = None

  response_payload = AgentResponse(
      session_id=client_managed_session_id,
      display_text=agent_dict_response.get("display_text", "No response text."),
      suggestions=agent_dict_response.get("suggestions"),
      structured_itinerary=parsed_itinerary,
      active_sub_agents=agent_dict_response.get("active_sub_agents"),
      requires_follow_up=agent_dict_response.get("requires_follow_up", False),
      error_message=agent_dict_response.get("error_message")
  )
  return response_payload

@app.post("/trips", status_code=201, response_model=Dict[str, str])
async def save_trip_api_endpoint(save_request: SaveTripRequest):
  global _firestore_client_initialized
  if not _firestore_client_initialized or not db_available:
    raise HTTPException(status_code=503, detail="Database service not available.")
  user_id_for_db = f"db_user_{save_request.client_session_id}"
  trip_id = save_trip_to_firestore(user_id=user_id_for_db, itinerary=save_request.itinerary_data)
  if trip_id:
    return {"trip_id": trip_id, "message": "Trip saved successfully."}
  else:
    raise HTTPException(status_code=500, detail="Failed to save trip.")

@app.get("/trips", response_model=List[TripSummary])
async def list_trips_api_endpoint(client_session_id: str, status: Optional[str] = "upcoming"):
  global _firestore_client_initialized
  if not _firestore_client_initialized or not db_available:
    raise HTTPException(status_code=503, detail="Database service not available.")
  user_id_for_db = f"db_user_{client_session_id}"
  trips_dict_list = get_trips_for_user_from_firestore(user_id=user_id_for_db, status=status)

  # Convert list of dicts to list of TripSummary Pydantic models
  validated_trips = []
  for trip_data_dict in trips_dict_list:
    try:
      # Pydantic V2: TripSummary.model_validate(trip_data_dict)
      # Pydantic V1:
      validated_trips.append(TripSummary(**trip_data_dict))
    except ValidationError as e:
      logging.error(f"ERROR (main.py): Invalid data for TripSummary for user {user_id_for_db}: {trip_data_dict}. Error: {e}")
      # Decide: skip this trip, or raise error, or return partial list?
      # For now, skipping invalid trip data.
  return validated_trips


@app.get("/trips/{trip_id}", response_model=Optional[Itinerary])
async def get_trip_details_api_endpoint(trip_id: str):
  global _firestore_client_initialized
  if not _firestore_client_initialized or not db_available:
    raise HTTPException(status_code=503, detail="Database service not available.")
  itinerary_model = get_trip_details_from_firestore(trip_id=trip_id)
  if itinerary_model:
    return itinerary_model
  raise HTTPException(status_code=404, detail=f"Trip with ID {trip_id} not found.")


@app.get("/health", summary="Health Check")
async def health_check():
  # ... (health check as before, ensuring it checks vertex_ai_client.IS_INITIALIZED) ...
  global _fastapi_agent_service_initialized, _firestore_client_initialized
  client_module_ok = vertex_ai_client and vertex_ai_client.IS_INITIALIZED
  service_status: Dict[str, Any] = {
      "status": "degraded",
      "agent_initialized_in_fastapi": _fastapi_agent_service_initialized,
      "client_module_flag_initialized": client_module_ok,
      "firestore_client_initialized": _firestore_client_initialized,
      "message": []
  }
  all_ok = True
  if not (_fastapi_agent_service_initialized and client_module_ok):
    service_status["message"].append("Agent service initialization pending or failed.")
    all_ok = False
  if not _firestore_client_initialized:
    service_status["message"].append("Firestore client initialization pending or failed.")
    all_ok = False
  if all_ok:
    service_status["status"] = "ok"
    service_status["message"].append("All services nominal.")
    return service_status
  else:
    service_status["message"] = " ".join(service_status["message"]) # type: ignore
    # Still return 200 for health check, but with degraded status
    return HTTPException(status_code=503, detail=service_status)


if __name__ == "__main__":
  import uvicorn
  print("INFO (main.py): Starting Uvicorn server programmatically for development...")
  uvicorn.run(app, host="127.0.0.1", port=8000)