
"""ATE dispatcher tests."""

import time
from typing import Any

import pytest

from ate_dispatcher import ATEDispatcher, ResultListener, Producer


class ExampleListener(ResultListener):
    def __init__(self, _id: int):
        super().__init__()
        self.id = _id
        self.result = []

    def process_dispatcher_result(self, topic: str, response: Any):
        self.result.append((response, topic))

    def reset(self):
        self.result = []


class ExampleProducer(Producer):
    def __init__(self, _id: int, timeout: float = 1000):
        super().__init__()
        self.id = _id
        self.timeout = timeout

    def produce_dispatcher_output(self, topic: str, *args, **kwargs) -> Any:
        time.sleep(self.timeout / 1000)
        return {
            'producer': self.id,
            'topic': topic,
            'args': args,
            'kwargs': kwargs
        }


@pytest.fixture(scope='module')
def dispatcher(request):
    ate_dispatcher = ATEDispatcher()
    ate_dispatcher.start()

    def teardown():
        ate_dispatcher.stop()

    request.addfinalizer(teardown)
    return ate_dispatcher


@pytest.fixture
def producers(request, dispatcher):
    producer_list = [ExampleProducer(_id, timeout=timeout)
                     for _id, timeout, _ in request.param]
    topics = [topic for _, _, topic in request.param]

    for producer, topic in zip(producer_list, topics):
        producer.start()
        dispatcher.register_result_producer(producer, topic)

    def teardown():
        for producer, topic in zip(producer_list, topics):
            dispatcher.deregister_result_producer(producer, topic)
            producer.stop()

    request.addfinalizer(teardown)
    return producer_list


@pytest.fixture
def listeners(request, dispatcher):
    listener_list = [ExampleListener(_id) for _id, _ in request.param]
    topics = [topic for _, topic in request.param]

    for listener, topic in zip(listener_list, topics):
        listener.start()
        dispatcher.register_result_listener(listener, topic)

    def teardown():
        for listener, topic in zip(listener_list, topics):
            dispatcher.deregister_result_listener(listener, topic)
            listener.stop()

    request.addfinalizer(teardown)
    return listener_list


@pytest.mark.parametrize(
    'producers, listeners',
    [[((0, 1000, 'a'), (1, 500, 'a')), ((0, 'a'), (1, 'a'))]], indirect=True)
def test_multiple_listeners_producers(dispatcher, producers, listeners):
    dispatcher.send_request('a', 3, 4, 5, ttl=4000, keyword='b')
    time.sleep(2)
    expected = [({
                    'producer': 1,
                    'topic': 'a',
                    'args': (3, 4, 5),
                    'kwargs': {'keyword': 'b'}
                }, 'a'),
                ({
                    'producer': 0,
                    'topic': 'a',
                    'args': (3, 4, 5),
                    'kwargs': {'keyword': 'b'}
                }, 'a')]

    assert all([listener.result == expected for listener in listeners])


@pytest.mark.parametrize(
    'producers, listeners',
    [[((0, 1000, 'a'), (1, 500, 'a')), ((0, 'a'), (1, 'a'))]], indirect=True)
def test_producer_timeout(dispatcher, producers, listeners):
    dispatcher.send_request('a', 3, 4, 5, ttl=600, keyword='b')
    time.sleep(2)
    expected = [({
                    'producer': 1,
                    'topic': 'a',
                    'args': (3, 4, 5),
                    'kwargs': {'keyword': 'b'}
                }, 'a')]
    assert all([listener.result == expected for listener in listeners])
