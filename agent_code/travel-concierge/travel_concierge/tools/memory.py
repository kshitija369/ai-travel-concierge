# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The 'memorize' tool for several agents to affect session states."""

from datetime import datetime
import json
import os
from typing import Dict, Any, List # Added List for type hinting
import smtplib # Added for sending emails

from email.mime.text import MIMEText # Added for creating email messages

from google.adk.agents.callback_context import CallbackContext
from google.adk.sessions.state import State
from google.adk.tools import ToolContext

from travel_concierge.shared_libraries import constants

SAMPLE_SCENARIO_PATH = os.getenv(
    "TRAVEL_CONCIERGE_SCENARIO", "eval/itinerary_empty_default.json"
)


def email_memorized_value(key: str, email_addresses: List[str], tool_context: ToolContext):
    """
    Emails a memorized string value to the provided list of email addresses.
    Ensures the email body is UTF-8 encoded.

    Args:
        key: The label indexing the memory to retrieve the value.
        email_addresses: A list of recipient email addresses.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    mem_dict = tool_context.state
    value_to_email = mem_dict.get(key)

    if value_to_email is None:
        return {"status": f'Error: Key "{key}" not found in memory.'}

    # Ensure the value is a string. For complex objects, consider json.dumps or a custom formatter.
    if not isinstance(value_to_email, str):
        try:
            # For complex objects, you might want to serialize to JSON or pretty print
            if isinstance(value_to_email, (dict, list)):
                 value_to_email_str = json.dumps(value_to_email, indent=2, ensure_ascii=False)
            else:
                value_to_email_str = str(value_to_email)
        except Exception as e:
            return {"status": f'Error: Value for key "{key}" could not be converted to a string representation: {e}'}
    else:
        value_to_email_str = value_to_email

    if not email_addresses or not isinstance(email_addresses, list) or not all(isinstance(em, str) for em in email_addresses):
        return {"status": "Error: Invalid email addresses provided. Must be a non-empty list of strings."}

    # --- Email Sending Logic ---
    # IMPORTANT: Replace with your actual email credentials and server details
    # It's highly recommended to use environment variables or a secrets manager for credentials.
    sender_email = os.environ.get("SENDER_EMAIL", "kshitija369@gmail.com")
    sender_password = os.environ.get("SENDER_APP_PASSWORD", "nueg zvcv qsyi mzlb") # Use an App Password
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))


    subject = f"Memorized Information: {key}"
    body = f"Hello,\n\nThe memorized value for '{key}' is:\n\n{value_to_email_str}\n\nRegards,\nAI Agent"

    # Create the email message with UTF-8 encoding for the body
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(email_addresses) # Comma-separated list for the 'To' header

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo() # Identify ourselves to the ESMTP server.
            server.starttls()  # Enable security
            server.ehlo() # Re-identify ourselves as an ESMTP client after STARTTLS.
            server.login(sender_email, sender_password)
            # sendmail's second argument (rcpttos) should be a list of recipient addresses
            server.sendmail(sender_email, email_addresses, msg.as_string())
        return {"status": f'Successfully emailed "{key}" to {", ".join(email_addresses)}.'}
    except smtplib.SMTPAuthenticationError:
        return {"status": "Error: Email authentication failed. Check your email/password or App Password setup."}
    except smtplib.SMTPServerDisconnected:
        return {"status": "Error: Could not connect to the SMTP server. Server might be down or incorrect."}
    except smtplib.SMTPRecipientsRefused as e:
        # e.recipients will be a dictionary of addresses that were refused
        refused_str = ", ".join([f"{addr}: {err}" for addr, err in e.recipients.items()])
        return {"status": f"Error: Some recipient email addresses were refused by the server: {refused_str}"}
    except smtplib.SMTPDataError as e:
        return {"status": f"Error: The SMTP server didn't accept the message data (code: {e.smtp_code}): {e.smtp_error}"}
    except Exception as e:
        return {"status": f'An unexpected error occurred while sending email: {e}'}
    # --- End Email Sending Logic ---



def memorize_list(key: str, value: str, tool_context: ToolContext):
    """
    Memorize pieces of information.

    Args:
        key: the label indexing the memory to store the value.
        value: the information to be stored.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    mem_dict = tool_context.state
    if key not in mem_dict:
        mem_dict[key] = []
    if value not in mem_dict[key]:
        mem_dict[key].append(value)
    return {"status": f'Stored "{key}": "{value}"'}


def memorize(key: str, value: str, tool_context: ToolContext):
    """
    Memorize pieces of information, one key-value pair at a time.

    Args:
        key: the label indexing the memory to store the value.
        value: the information to be stored.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    mem_dict = tool_context.state
    mem_dict[key] = value
    return {"status": f'Stored "{key}": "{value}"'}




def forget(key: str, value: str, tool_context: ToolContext):
    """
    Forget pieces of information.

    Args:
        key: the label indexing the memory to store the value.
        value: the information to be removed.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    if tool_context.state[key] is None:
        tool_context.state[key] = []
    if value in tool_context.state[key]:
        tool_context.state[key].remove(value)
    return {"status": f'Removed "{key}": "{value}"'}


def _set_initial_states(source: Dict[str, Any], target: State | dict[str, Any]):
    """
    Setting the initial session state given a JSON object of states.

    Args:
        source: A JSON object of states.
        target: The session state object to insert into.
    """
    if constants.SYSTEM_TIME not in target:
        target[constants.SYSTEM_TIME] = str(datetime.now())

    if constants.ITIN_INITIALIZED not in target:
        target[constants.ITIN_INITIALIZED] = True

        target.update(source)

        itinerary = source.get(constants.ITIN_KEY, {})
        if itinerary:
            target[constants.ITIN_START_DATE] = itinerary[constants.START_DATE]
            target[constants.ITIN_END_DATE] = itinerary[constants.END_DATE]
            target[constants.ITIN_DATETIME] = itinerary[constants.START_DATE]


def _load_precreated_itinerary(callback_context: CallbackContext):
    """
    Sets up the initial state.
    Set this as a callback as before_agent_call of the root_agent.
    This gets called before the system instruction is contructed.

    Args:
        callback_context: The callback context.
    """    
    data = {}
    with open(SAMPLE_SCENARIO_PATH, "r") as file:
        data = json.load(file)
        print(f"\nLoading Initial State: {data}\n")

    _set_initial_states(data["state"], callback_context.state)
