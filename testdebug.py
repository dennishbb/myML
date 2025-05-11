#!/usr/bin/env python
# coding: utf-8

# In[1]:


# Simple Python script for testing and debugging

def greet(name):
    """A simple function that greets the user."""
    return f"Hello, {name}!"

def calculate_sum(a, b):
    """A function that calculates the sum of two numbers."""
    return a + b

def main():
    # Variables
    user_name = "Alice"
    num1 = 10
    num2 = 20

    # Function calls
    greeting = greet(user_name)
    total = calculate_sum(num1, num2)

    # Output results
    print(greeting)
    print(f"The sum of {num1} and {num2} is {total}")

    # Loop example
    print("Counting to 5:")
    for i in range(1, 6):
        print(i)

if __name__ == "__main__":
    main()

