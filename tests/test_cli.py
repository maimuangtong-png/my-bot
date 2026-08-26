import unittest


from python_project.cli import greeting


class GreetingTests(unittest.TestCase):
    def test_greeting_uses_default_name(self) -> None:
        self.assertEqual(greeting(), "Hello from Python Project!")

    def test_greeting_accepts_a_name(self) -> None:
        self.assertEqual(greeting("Ada"), "Hello from Ada!")