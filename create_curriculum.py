import os

base = r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue'
os.makedirs(os.path.join(base, 'curriculum'), exist_ok=True)

# A1.yaml
a1 = """level: "A1"
name: "Principiante"
description: "Comunicación básica en situaciones cotidianas"
vocabulary_target: 150
grammar_topics:
  - "Present Simple (to be, have, regular verbs)"
  - "Present Continuous"
  - "Basic questions (who, what, where, when, how)"
  - "There is / There are"
  - "Prepositions of place (in, on, at, under, next to)"
  - "Possessive adjectives (my, your, his, her)"
  - "Imperatives"
units:
  - id: "A1-u1"
    title: "Presentaciones y Saludos"
    vocabulary: ["hello", "goodbye", "name", "nice to meet you", "how are you"]
    grammar: ["to be (I am, you are)", "subject pronouns"]
    phrases: ["Hello, I'm [name]", "Nice to meet you", "How are you?"]
    objectives:
      - "Presentarse a sí mismo"
      - "Saludar y despedirse"
      - "Preguntar y responder 'How are you?'"
  - id: "A1-u2"
    title: "Familia y Amigos"
    vocabulary: ["mother", "father", "brother", "sister", "friend", "family"]
    grammar: ["possessive adjectives", "have got"]
    phrases: ["This is my mother", "I have a brother", "She's my friend"]
    objectives:
      - "Describir familia"
      - "Usar 'have got' para posesión"
  - id: "A1-u3"
    title: "Comida y Bebida"
    vocabulary: ["apple", "bread", "water", "milk", "rice", "chicken", "like", "eat", "drink"]
    grammar: ["like + -ing", "countable/uncountable", "some/any"]
    phrases: ["I like apples", "I'd like some water", "Do you like rice?"]
    objectives:
      - "Pedir comida y bebida"
      - "Expresar gustos con like"
  - id: "A1-u4"
    title: "Rutina Diaria"
    vocabulary: ["wake up", "brush teeth", "breakfast", "work", "study", "sleep", "time"]
    grammar: ["present simple routines", "adverbs of frequency", "telling time"]
    phrases: ["I wake up at 7", "I usually have breakfast", "What time is it?"]
    objectives:
      - "Describir rutina diaria"
      - "Decir la hora"
  - id: "A1-u5"
    title: "Lugares y Direcciones"
    vocabulary: ["street", "turn left", "turn right", "straight", "near", "far", "bank", "supermarket"]
    grammar: ["imperatives", "prepositions of place", "there is/there are"]
    phrases: ["Turn left", "It's near the bank", "Where is the supermarket?"]
    objectives:
      - "Pedir y dar direcciones"
      - "Describir ubicación"
assessment:
  vocabulary_min: 100
  grammar_score_min: 70
  speaking_tasks:
    - "Present yourself in 30 seconds"
    - "Describe your family"
    - "Order food in a restaurant"
"""
with open(os.path.join(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\curriculum', 'A1.yaml'), 'w', encoding='utf-8') as f:
    f.write("level: \"A1\"\nname: \"Principiante\"\ndescription: \"Comunicación básica en situaciones cotidianas\"\nvocabulary_target: 150\ngrammar_topics:\n  - \"Present Simple (to be, have, regular verbs)\"\n  - \"Present Continuous\"\n  - \"Basic questions (who, what, where, when, how)\"\n  - \"There is / There are\"\n  - \"Prepositions of place (in, on, at, under, next to)\"\n  - \"Possessive adjectives (my, your, his, her)\"\n  - \"Imperatives\"\nunits:\n  - id: \"A1-u1\"\n    title: \"Presentaciones y Saludos\"\n    vocabulary: [\"hello\", \"goodbye\", \"name\", \"nice to meet you\", \"how are you\"]\n    grammar: [\"to be (I am, you are)\", \"subject pronouns\"]\n    phrases: [\"Hello, I'm [name]\", \"Nice to meet you\", \"How are you?\"]\n    objectives:\n      - \"Presentarse a sí mismo\"\n      - \"Saludar y despedirse\"\n      - \"Preguntar y responder 'How are you?'\"\n  - id: \"A1-u2\"\n    title: \"Familia y Amigos\"\n    vocabulary: [\"mother\", \"father\", \"brother\", \"sister\", \"friend\", \"family\"]\n    grammar: [\"possessive adjectives\", \"have got\"]\n    phrases: [\"This is my mother\", \"I have a brother\", \"She's my friend\"]\n    objectives:\n      - \"Describir familia\"\n      - \"Usar 'have got' para posesión\"\n  - id: \"A1-u3\"\n    title: \"Comida y Bebida\"\n    vocabulary: [\"apple\", \"bread\", \"water\", \"milk\", \"rice\", \"chicken\", \"like\", \"eat\", \"drink\"]\n    grammar: [\"like + -ing\", \"countable/uncountable\", \"some/any\"]\n    phrases: [\"I like apples\", \"I'd like some water\", \"Do you like rice?\"]\n    objectives:\n      - \"Pedir comida y bebida\"\n      - \"Expresar gustos con like\"\n  - id: \"A1-u4\"\n    title: \"Rutina Diaria\"\n    vocabulary: [\"wake up\", \"brush teeth\", \"breakfast\", \"work\", \"study\", \"sleep\", \"time\"]\n    grammar: [\"present simple routines\", \"adverbs of frequency\", \"telling time\"]\n    phrases: [\"I wake up at 7\", \"I usually have breakfast\", \"What time is it?\"]\n    objectives:\n      - \"Describir rutina diaria\"\n      - \"Decir la hora\"\n  - id: \"A1-u5\"\n    title: \"Lugares y Direcciones\"\n    vocabulary: [\"street\", \"turn left\", \"turn right\", \"straight\", \"near\", \"far\", \"bank\", \"supermarket\"]\n    grammar: [\"imperatives\", \"prepositions of place\", \"there is/there are\"]\n    phrases: [\"Turn left\", \"It's near the bank\", \"Where is the supermarket?\"]\n    objectives:\n      - \"Pedir y dar direcciones\"\n      - \"Describir ubicación\"\nassessment:\n  vocabulary_min: 100\n  grammar_score_min: 70\n  speaking_tasks:\n    - \"Present yourself in 30 seconds\"\n    - \"Describe your family\"\n    - \"Order food in a restaurant\"\n")
print('A1.yaml created')