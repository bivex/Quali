"""Sample Python file with intentional code smells for testing Quali2."""

import os
import sys
import json
import re
import datetime
import collections
import itertools
import functools
import pathlib
import typing
import logging

import pandas as pd
import numpy as np
import torch

MAGIC = 42
ANOTHER_MAGIC = 31337


class Animal:
    legs = 4
    sound = ""

    def __init__(self, name, age, weight, color, breed, height):
        self.name = name
        self.age = age
        self.weight = weight
        self.color = color
        self.breed = breed
        self.height = height

    def speak(self):
        return self.sound

    def walk(self):
        return f"{self.name} walks on {self.legs} legs"

    def eat(self, food):
        return f"{self.name} eats {food}"

    def sleep(self, hours):
        return f"{self.name} sleeps for {hours} hours"

    def run(self, speed):
        return f"{self.name} runs at {speed} mph"

    def jump(self, height):
        return f"{self.name} jumps {height} feet"

    def swim(self, distance):
        return f"{self.name} swims {distance} meters"

    def fly(self, altitude):
        return f"{self.name} flies at {altitude} feet"

    def rest(self):
        return f"{self.name} is resting"

    def play(self, toy):
        return f"{self.name} plays with {toy}"

    def groom(self):
        return f"{self.name} is being groomed"

    def train(self, trick):
        return f"{self.name} learns {trick}"

    def vaccinate(self, vaccine):
        return f"{self.name} gets {vaccine} vaccine"

    def weigh(self):
        return f"{self.name} weighs {self.weight} kg"

    def measure(self):
        return f"{self.name} is {self.height} cm tall"

    def describe(self):
        return f"{self.name} is a {self.color} {self.breed}"


class Dog(Animal):
    sound = "Woof"

    def __init__(self, name, age, weight, color, breed, height, owner):
        self.name = name
        self.age = age
        self.weight = weight
        self.color = color
        self.breed = breed
        self.height = height
        self.owner = owner

    def fetch(self, item):
        return f"{self.name} fetches {item}"

    def bark(self):
        return "Woof Woof!"

    def wag_tail(self):
        return f"{self.name} wags tail"


class Cat(Animal):
    sound = "Meow"

    def __init__(self, name, age, weight, color, breed, height, indoor):
        self.name = name
        self.age = age
        self.weight = weight
        self.color = color
        self.breed = breed
        self.height = height
        self.indoor = indoor

    def purr(self):
        return "Purrrr"

    def scratch(self, target):
        return f"{self.name} scratches {target}"


class Bird(Animal):
    sound = "Tweet"

    def __init__(self, name, age, weight, color, breed, height, can_fly):
        self.name = name
        self.age = age
        self.weight = weight
        self.color = color
        self.breed = breed
        self.height = height
        self.can_fly = can_fly

    def chirp(self):
        return "Chirp chirp!"


class Fish(Animal):
    sound = "Blub"

    def __init__(self, name, age, weight, color, breed, height, saltwater):
        self.name = name
        self.age = age
        self.weight = weight
        self.color = color
        self.breed = breed
        self.height = height
        self.saltwater = saltwater

    def bubble(self):
        return "Blub blub"


class Hamster(Animal):
    sound = "Squeak"

    def __init__(self, name, age, weight, color, breed, height, wheel):
        self.name = name
        self.age = age
        self.weight = weight
        self.color = color
        self.breed = breed
        self.height = height
        self.wheel = wheel

    def spin(self):
        return f"{self.name} spins the wheel"


class Reptile(Animal):
    sound = "Hiss"

    def __init__(self, name, age, weight, color, breed, height, cold_blooded):
        self.name = name
        self.age = age
        self.weight = weight
        self.color = color
        self.breed = breed
        self.height = height
        self.cold_blooded = cold_blooded

    def bask(self):
        return f"{self.name} basks in the sun"


class Horse(Animal):
    sound = "Neigh"

    def __init__(self, name, age, weight, color, breed, height, rider):
        self.name = name
        self.age = age
        self.weight = weight
        self.color = color
        self.breed = breed
        self.height = height
        self.rider = rider

    def gallop(self):
        return f"{self.name} gallops with {self.rider}"


def complex_function(a, b, c, d, e, f, g, h):
    result = 0
    if a > 0 and b > 0 and c > 0 and d > 0 and e > 0:
        if f > 0 and g > 0 and h > 0:
            result = a + b + c + d + e + f + g + h
        elif f > 0 or g > 0:
            result = a + b + c
        elif a > 10 and b < 20 and c != 5 and d >= 1 and e <= 100:
            result = a * b * c
        else:
            result = 42
    elif a < 0:
        result = -a
    elif b < 0:
        result = -b
    elif c < 0:
        result = -c
    return result


def function_with_magic_numbers():
    x = 3.14159 * 2.71828
    y = x * 42 + 31337 - 8080
    z = y / 255 * 1024
    return z


def function_with_long_statement():
    very_long_variable = "this is an extremely long string that goes on and on and on and makes the line way too long for anyone to read comfortably without horizontal scrolling which is really annoying in code review"
    return very_long_variable


def handle_errors():
    try:
        x = int("not a number")
    except ValueError:
        pass

    try:
        y = 1 / 0
    except ZeroDivisionError:
        ...

    try:
        z = [1, 2, 3][10]
    except IndexError:
        pass


def process_data():
    try:
        df = pd.DataFrame({"a": [1, 2, np.nan], "b": [4, np.nan, 6]})

        result = df["a"]["b"]

        check = df == np.nan

        merged = df.merge(df)

        for i, row in df.iterrows():
            print(row)

        values = df.values
    except Exception:
        pass


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = torch.nn.Linear(10, 5)

    def forward(self, x):
        return self.fc(x)


def use_model():
    model = Model()
    x = torch.randn(1, 10)
    result = model.forward(x)
    return result


def chained_access(data):
    return data.config.settings.options.values.enabled


long_lambda = lambda x, y, z, w: (
    x + y + z + w if x > 0 and y > 0 else x * y * z * w if x < 0 else 0
)
