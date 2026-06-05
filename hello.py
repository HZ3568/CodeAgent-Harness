import sys
from typing import Optional


def greet(name: str = "World", greeting_type: str = "hello") -> str:
    """
    Generate a greeting string.
    
    Args:
        name (str): The name to greet. Defaults to "World".
        greeting_type (str): The type of greeting ('hello', 'goodbye', 'hi'). Defaults to 'hello'.
        
    Returns:
        str: A greeting string in the format "{Greeting}, {name}!"
    """
    greetings = {
        "hello": "Hello",
        "goodbye": "Goodbye", 
        "hi": "Hi",
        "welcome": "Welcome"
    }
    
    greeting = greetings.get(greeting_type.lower(), "Hello")
    return f"{greeting}, {name}!"


def parse_args() -> tuple[str, str]:
    """
    Parse command line arguments.
    
    Returns:
        tuple: A tuple containing (name, greeting_type)
    """
    name = sys.argv[1] if len(sys.argv) > 1 else "World"
    greeting_type = sys.argv[2] if len(sys.argv) > 2 else "hello"
    return name, greeting_type


def main() -> None:
    """
    Main function to print the greeting.
    """
    try:
        name, greeting_type = parse_args()
        print(greet(name, greeting_type))
    except IndexError:
        print(greet())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print(greet())  # Fallback to default greeting


if __name__ == "__main__":
    main()