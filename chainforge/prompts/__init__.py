"""Prompt Templates — variable injection, composition, chat templates.

Provides:
  - PromptTemplate: parameterized string templates
  - ChatPromptTemplate: structured multi-message templates
  - FewShotPromptTemplate: example-based prompting
  - MessagePlaceholder: dynamic message insertion

Usage:
    from chainforge.prompts import PromptTemplate, ChatPromptTemplate

    tmpl = PromptTemplate("Hello, {name}!")
    print(tmpl.format(name="World"))

    chat = ChatPromptTemplate.from_messages([
        ("system", "You are a {role} assistant."),
        ("user", "{input}"),
    ])
    messages = chat.format_messages(role="helpful", input="Hi!")
"""

from chainforge.prompts.template import PromptTemplate, FewShotPromptTemplate
from chainforge.prompts.chat import ChatPromptTemplate, MessagePlaceholder
from chainforge.prompts.hub import PromptHub

__all__ = [
    "PromptTemplate",
    "FewShotPromptTemplate",
    "ChatPromptTemplate",
    "MessagePlaceholder",
    "PromptHub",
]
