import unittest
from hello import greet


class TestHello(unittest.TestCase):
    """
    Unit tests for the hello module.
    """
    
    def test_greet_default(self):
        """Test greet function with default parameters."""
        self.assertEqual(greet(), "Hello, World!")
    
    def test_greet_custom_name(self):
        """Test greet function with custom name."""
        self.assertEqual(greet("Alice"), "Hello, Alice!")
    
    def test_greet_different_types(self):
        """Test greet function with different greeting types."""
        self.assertEqual(greet("Bob", "hi"), "Hi, Bob!")
        self.assertEqual(greet("Charlie", "goodbye"), "Goodbye, Charlie!")
        self.assertEqual(greet("Diana", "welcome"), "Welcome, Diana!")
    
    def test_greet_invalid_type(self):
        """Test greet function with invalid greeting type (should default to Hello)."""
        self.assertEqual(greet("Eve", "invalid"), "Hello, Eve!")


if __name__ == "__main__":
    unittest.main()