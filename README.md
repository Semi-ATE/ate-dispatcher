# ate-dispatcher

[![Project License - MIT](https://img.shields.io/pypi/l/ate-dispatcher.svg)](./LICENSE.txt)
[![pypi version](https://img.shields.io/pypi/v/ate-dispatcher.svg)](https://pypi.org/project/ate-dispatcher/)
[![conda version](https://img.shields.io/conda/vn/conda-forge/ate-dispatcher.svg)](https://www.anaconda.com/download/)
[![download count](https://img.shields.io/conda/dn/conda-forge/ate-dispatcher.svg)](https://www.anaconda.com/download/)
[![Downloads](https://pepy.tech/badge/ate-dispatcher)](https://pepy.tech/project/ate-dispatcher)
[![PyPI status](https://img.shields.io/pypi/status/ate-dispatcher.svg)](https://github.com/Semi-ATE/ate-dispatcher)
[![Unit tests](https://github.com/Semi-ATE/ate-dispatcher/actions/workflows/test_python.yml/badge.svg)](https://github.com/Semi-ATE/ate-dispatcher/actions/workflows/test_python.yml)
[![codecov](https://codecov.io/gh/Semi-ATE/ate-dispatcher/branch/main/graph/badge.svg?token=5MLBM0PHLL)](https://codecov.io/gh/Semi-ATE/ate-dispatcher)


## Overview
A pure-Python, thread-based, asynchronous dispatcher used to gather results
from distributed agents that react on a given event.

The dispatcher reacts to an event tagged with a given topic, which is relayed
to a set of `Producer` objects (which registered the kind of
events they react to). Each result is then passed to a set of `ResultListener`
objects, which will attend to the response depending if they were registered
to attend the given topic.

The exposed API is thread-safe, asynchronous and lock-free, which makes it
suitable for tasks that are lightweight and quick.

## Dependencies
This package is pure-Python, and therefore it does not depend on any external
library, besides `typing-extensions`, which is used to import the typing
classes that are not available in older Python 3 versions.

## Installation
You can install this library by using conda or pip package managers,
as it follows:

```bash
# Using conda
conda install ate-dispatcher -c conda-forge

# Using pip
pip install ate-dispatcher
```

## Local development
In order to install a local development version for `ate-dispatcher`, it is
possible to invoke pip:

```bash
pip install -e .
```

## Package usage
`ate-dispatcher` exposes two abstract interfaces (`Producer` and `ResultListener`)
as well as the main dispatcher (`ATEDispatcher`). The former classes are designed
to be inherited, while the last one is designed to be instantiated.

### Defining a producer
A `Producer` object is on charge of producing a response to an incoming input
message from the dispatcher that is tagged with a certain `topic` that the
object can handle. It must implement `produce_dispatcher_output`.


```python
import time
from typing import Any
from ate_dispatcher import Producer

# Defining a producer
class SpecificTopicProducer(Producer):
    def __init__(self, _id: int, timeout: int, *topics):
        super().__init__()
        self.id = _id
        self.timeout = timeout / 1000
        self.topics = set(topics)

    def produce_dispatcher_output(
            self, topic: str, *args, **kwargs) -> Any:
        time.sleep(timeout)
        return {
            'id': self.id,
            'some_key': topic,
            'args': args,
            'kwargs': kwargs
        }
```

### Defining a result listener
A `ResultListener` object will receive the responses emitted by the `Producer`
objects that reacted to a given topic that the listener also supports. This
is the endpoint for the dispatcher architecture, where all end messages will
arrive. The `ResultListener` subclasses must implement the
`process_dispatcher_result` method.

```python
from typing import Any
from ate_dispatcher import ResultListener

# Defining a result listener
class ResultListenerExample(ResultListener):
    def __init__(self):
        super().__init__()
        self.responses = {}

    def clear(self):
        self.responses = {}

    def process_dispatcher_result(self, topic: str, response: Any):
        topic_responses = self.responses.get(topic, [])
        topic_responses.append(response)
        self.responses[topic] = topic_responses

```

### Creating, using and destroying the dispatcher
After defining the `Producer` and `ResultListener` subclasses, it is necessary
to instantiate and register the `ATEDispatcher instance`. Since the interfaces
inherit from `threading.Thread`, it is necessary to keep track of their
lifetime via the `start` and `end` methods.

```python
import time

# Import the producer and result listener classes
from specific_topic_producer import SpecificTopicProducer
from result_listener_example import ResultListenerExample

# Import the dispatcher
from ate_dispatcher import ATEDispatcher

# Create the dispatcher
dispatcher = ATEDispatcher()

# Start the dispatcher, the lifetime is delegated to the end developer.
dispatcher.start()

# Define the producers and register them against the dispatcher
producer1 = SpecificTopicProducer(0, 200, 'topic1', 'my_topic')
producer1.start()

producer2 = SpecificTopicProducer(1, 500, 'topic1', 'topic2', 'my_topic')
producer2.start()

for topic in producer1.topics:
    dispatcher.register_result_producer(producer1, topic)

for topic in producer2.topics:
    dispatcher.register_result_producer(producer2, topic)

# Define the result listeners and register them against the dispatcher
listener1 = ResultListenerExample()
listener1.start()

listener2 = ResultListenerExample()
listener2.start()

for topic in ['topic1', 'topic2', 'my_topic']:
    # The first listener will receive all responses tagged with all topics
    dispatcher.register_result_listener(listener1, topic)

for topic in ['topic1', 'my_topic']:
    # This listener will attend to certain topics.
    dispatcher.register_result_listener(listener2, topic)
```

Since the dispatcher architecture is completely asynchronous, a trigger message
may indicate a maximum timeout (in milliseconds) for all registered producers
on a given topic to emit their response. Any response received after the
specified timeout will be discarded. Also, the messages will be delivered to
the result listeners as they arrive.

```python
# Trigger a dispatcher request with a 4000ms timeout on the topic1
dispatcher.send_request('topic1', 3, 4, 5, ttl=4000, keyword='b')

# Wait for responses to arrive
time.sleep(1.0)

# Both listeners should have received the responses from both producers.
expected_responses = {
    'topic1': [
        {
            'id': 0
            'some_key': 'topic1',
            'args': (3, 4, 5),
            'kwargs': {
                'keyword': 'b'
            }
        },
        {
            'id': 1
            'some_key': 'topic1',
            'args': (3, 4, 5),
            'kwargs': {
                'keyword': 'b'
            }
        },
    ]
}

assert listener1.responses == expected_responses
assert listener2.responses == expected_responses

# Clear the listener responses
listener1.clear()
listener2.clear()

# Trigger a dispatcher request with a 300ms timeout limit on the topic my_topic
dispatcher.send_request('my_topic', 3, 4, 5, ttl=300, keyword='b')

# Wait for responses to arrive
time.sleep(0.5)

# Both listeners should have only received the response from producer1.
expected_responses = {
    'my_topic': [
        {
            'id': 0
            'some_key': 'my_topic',
            'args': (3, 4, 5),
            'kwargs': {
                'keyword': 'b'
            }
        }
    ]
}

assert listener1.responses == expected_responses
assert listener2.responses == expected_responses


# Clear the listener1 responses
listener1.clear()

# Trigger a dispatcher request with a 1000ms timeout limit on the topic topic2
dispatcher.send_request('topic2', 3, 4, 5, ttl=1000, keyword='b')

# Wait for responses to arrive
time.sleep(1.0)

# Only the listener1 should have received the message produced by the producer2
expected_responses = {
    'topic2': [
        {
            'id': 1
            'some_key': 'topic2',
            'args': (3, 4, 5),
            'kwargs': {
                'keyword': 'b'
            }
        }
    ]
}

assert listener1.responses == expected_responses
```

Finally, each registered `Producer` and `ResultListener` instance can be
deregistered from an specific topic at any time. However, before stopping either
`Producer` or `ResultListener` instances, each registered topic must be
deregistered.

```python
# Deregister the listener2 and the producer1 from certain topics
dispatcher.deregister_result_listener(listener2, 'my_topic')
dispatcher.deregister_result_producer(producer1, 'topic1')

# Stopping the producer and result listener instances
for topic in producer1.topics:
    dispatcher.deregister_result_producer(producer1, topic)

for topic in producer2.topics:
    dispatcher.deregister_result_producer(producer2, topic)

producer1.stop()
producer2.stop()

for topic in ['topic1', 'topic2', 'my_topic']:
    dispatcher.deregister_result_listener(listener1, topic)

for topic in ['topic1', 'my_topic']:
    dispatcher.deregister_result_listener(listener2, topic)

# Stop the dispatcher
dispatcher.stop()
```

## Running tests
We use pytest to run tests as it follows:

```bash
pytest -x -v ate_dispatcher/tests
```

## Changelog
Visit our [CHANGELOG](CHANGELOG.md) file to learn more about our new features and improvements.

## Contribution guidelines
We follow PEP8 and PEP257. We use MyPy type annotations for all functions and classes declared on this package. Feel free to send a PR or create an issue if you have any problem/question.
