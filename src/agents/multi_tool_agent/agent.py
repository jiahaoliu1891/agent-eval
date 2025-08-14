import asyncio
import datetime
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The weather in New York is sunny with a temperature of 25 degrees"
                " Celsius (77 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """

    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": (
                f"Sorry, I don't have timezone information for {city}."
            ),
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = (
        f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
    )
    return {"status": "success", "report": report}


root_agent = Agent(
    name="weather_time_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to answer questions about the time and weather in a city."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about the time and weather in a city."
    ),
    tools=[get_weather, get_current_time],
)

eval_agent = Agent(
    name="eval_agent",
    model="gemini-2.0-flash",
    description="Simulated human agent for evaluation",
    instruction=(
        "You are a human"
        "You are talking to a weather and time agent who can answer questions about the time and weather in a city."
        "You want to know new york's weather." 
        "After you get the answer, reply <STOP> to end the conversation."
    )
)


async def run_repl():
    app_name = "weather_time_repl"
    user_id = "repl_user"
    session_id = "repl_session"

    """REPL loop for agent interaction."""
    session_service = InMemorySessionService()
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    runner = Runner(
        agent=root_agent,
        app_name=app_name,
        session_service=session_service
    )

    # REPL loop
    while True:
        try:
            # Get user input
            user_input = input("> ").strip()
            
            # Handle special commands
            if user_input.lower() == "/exit":
                break
            elif user_input.lower() == "/clear":
                print("\033[2J\033[H")  # Clear terminal
                continue
            elif not user_input:
                continue
            
            # Create user message
            user_content = types.Content(
                role='user',
                parts=[types.Part(text=user_input)]
            )
            
            # Execute agent and stream response
            final_response_text = ""
            async for event in runner.run_async(
                user_id=user_id, session_id=session_id, new_message=user_content
            ):
                if event.partial and event.content and event.content.parts and event.content.parts[0].text:
                    print(event.content.parts[0].text, end="", flush=True)

                if event.is_final_response():
                    if event.content and event.content.parts and event.content.parts[0].text:
                        final_response_text = event.content.parts[0].text
                    elif getattr(event, "error_message", None):
                        final_response_text = f"[error] {event.error_message}"
                    print()
                    break

            if final_response_text:
                print(final_response_text)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue


async def run_eval():
    app_name = "agent_eval"
    user_id = "eval_user"
    

    eval_session_service = InMemorySessionService()
    eval_session_id = "eval_session"
    await eval_session_service.create_session(app_name=app_name, user_id=user_id, session_id=eval_session_id)
    eval_runner = Runner(
        agent=eval_agent,
        app_name=app_name,
        session_service=eval_session_service
    )

    root_session_service = InMemorySessionService()
    root_session_id = "root_session"
    await root_session_service.create_session(app_name=app_name, user_id=user_id, session_id=root_session_id)
    root_runner = Runner(
        agent=root_agent,
        app_name=app_name,
        session_service=root_session_service
    )

    MAX_ITERATIONS = 3

    # Initial message to the eval agent
    initial_message = types.Content(
        role='user',
        parts=[types.Part(text="Hi how can I help you?")]
    )


    for i in range(MAX_ITERATIONS):
        print(f"========== Iteration {i+1} ==========")
        eval_agent_response = ""
        if i == 0:
            eval_agent_input_message = initial_message
        else:
            eval_agent_input_message = types.Content(
                role='user',
                parts=[types.Part(text=root_agent_response)]
            )

        # Run the eval agent
        async for event in eval_runner.run_async(
            user_id=user_id, session_id=eval_session_id, new_message=eval_agent_input_message
        ):
            if event.is_final_response():
                eval_agent_response = event.content.parts[0].text
                break
    
        print(f"[Eval Agent]: {eval_agent_response}")
        if "<STOP>" in eval_agent_response:
            print("Eval agent stopped the conversation.")
            break

        # Run the root agent
        root_agent_response = ""
        root_agent_input_message = types.Content(
            role='user',
            parts=[types.Part(text=eval_agent_response)]
        )
        async for event in root_runner.run_async(
            user_id=user_id, session_id=root_session_id, new_message=root_agent_input_message
        ):
            if event.is_final_response():
                root_agent_response = event.content.parts[0].text
                break
        print(f"[Root Agent]: {root_agent_response}")

    
if __name__ == "__main__":
    try:
        asyncio.run(run_eval())
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)