
"""General dispatcher declarations and utilities."""

import sys
import time
import threading
from uuid import uuid4
from queue import Queue
from typing import Any, Dict, Set, Optional, Tuple

if sys.version_info >= (3, 8):
    from typing import TypedDict, Literal
else:
    from typing_extensions import TypedDict, Literal

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired


class QueueMsg(TypedDict):
    kind: Literal['exit', 'request', 'reply']
    topic: Optional[str]
    args: Tuple
    kwargs: Dict
    uuid: NotRequired[str]
    reply_to: NotRequired[Queue]


class PendingMessage(TypedDict):
    ttl: float
    emit_time: float
    missing: int


class ResultListener(threading.Thread):
    """
    Base class used to declare a dispatcher result receiver.

    Notes
    -----
    As a :class:`threading.Thread` subclass, each `ResultListener` instance
    requires a call to `start` and `stop` in order to process messages and
    stopping, respectively.
    """

    def __init__(self):
        super().__init__()
        self._listener_queue = Queue()

    def run(self) -> None:
        while True:
            msg: QueueMsg = self._listener_queue.get()
            kind = msg['kind']
            if kind == 'exit':
                break
            elif kind == 'reply':
                topic = msg['topic']
                response = msg['args']
                self.process_dispatcher_result(topic, *response)

    def stop(self):
        msg = QueueMsg(kind='exit', topic=None, args=tuple(),
                       kwargs={}, reply_to=None)
        self._listener_queue.put(msg)

    def send_result(self, topic: str, *response: Tuple[Any]):
        msg = QueueMsg(
            kind='reply', topic=topic, args=response, kwargs={},
            uuid=None, reply_to=None)
        self._listener_queue.put(msg)

    def process_dispatcher_result(self, topic: str, response: Any):
        """
        Process a response message emitted by the main dispatcher for the
        topic `topic`.

        Parameters
        ----------
        topic: str
            The topic on which the result was dispatched.
        response: Any
            The actual response body.

        Notes
        -----
        As the dispatching mechanism is asynchronous and there might exist
        multiple result producers, this method might get called multiple times.
        """
        raise NotImplementedError(
            f'{type(self).__qualname__} has not implemented '
            'the process_dispatcher_result method')


class Producer(threading.Thread):
    """
    Base class to declare a dispatcher request producer.

    Notes
    -----
    As a :class:`threading.Thread` subclass, each `ResultListener` instance
    requires a call to `start` and `stop` in order to process messages and
    stopping, respectively.
    """

    def __init__(self):
        super().__init__()
        self._producer_queue = Queue()

    def run(self):
        while True:
            msg: QueueMsg = self._producer_queue.get()
            kind = msg['kind']
            if kind == 'exit':
                break
            elif kind == 'request':
                topic = msg['topic']
                args = msg['args']
                kwargs = msg['kwargs']
                reply_to = msg['reply_to']
                uuid = msg['uuid']
                result = self.produce_dispatcher_output(
                    topic, *args, **kwargs)
                reply = QueueMsg(kind='reply', topic=topic,
                                 args=(result,), kwargs={}, uuid=uuid,
                                 reply_to=None)
                reply_to.put(reply)

    def stop(self):
        msg = QueueMsg(kind='exit', topic=None, args=tuple(),
                       kwargs={}, reply_to=None)
        self._producer_queue.put(msg)

    def submit_producer_message(self, topic: str, uuid: str,
                                reply_to: Queue, *args, **kwargs):
        msg = QueueMsg(
            kind='request', topic=topic, args=args, kwargs=kwargs,
            uuid=uuid, reply_to=reply_to)
        self._producer_queue.put(msg)

    def produce_dispatcher_output(
            self, topic: str, *args, **kwargs) -> Any:
        """
        Retrieve and/or produce the output required by the ATEDispatcher
        on a given topic.

        Parameters
        ----------
        topic: str
            The topic on which the result should be dispatched on.
        args: tuple
            Tuple containing the variadic positional arguments.
        kwargs: dict
            Dictionary containing the optional keyword arguments.

        Returns
        -------
        response: Any
            The actual response expected by the dispatcher.
        """
        raise NotImplementedError(
            'A producer must implement `produce_dispatcher_output`')


class ATEDispatcher(threading.Thread):
    """
    General-purpose function dispatcher

    This class takes an input request with a given identifier, dispatches it
    to a set of producers and relays their response to another set of
    reply listeners.
    """

    def __init__(self):
        super().__init__()
        self.evt_result_listeners: Dict[str, Set[ResultListener]] = {}
        self.evt_producers: Dict[str, Set[Producer]] = {}
        self.pending_responses: Dict[str, PendingMessage] = {}
        self.queue = Queue()

    def run(self):
        while True:
            msg: QueueMsg = self.queue.get()
            msg_kind = msg['kind']
            topic = msg['topic']
            if msg_kind == 'exit':
                for topic in self.evt_result_listeners:
                    result_listeners = self.evt_result_listeners[topic]
                    for result_listener in result_listeners:
                        result_listener.stop()
                for topic in self.evt_producers:
                    producers = self.evt_producers[topic]
                    for producer in producers:
                        producer.stop()
                break
            elif msg_kind == 'request':
                evt_producers = self.evt_producers.get(topic, set({}))
                _id = str(uuid4())
                args = msg['args']
                kwargs = msg['kwargs']
                ttl = kwargs.pop('ttl', 5000)
                cur_time = time.time()
                self.pending_responses[_id] = PendingMessage(
                    ttl=ttl, emit_time=cur_time, missing=len(evt_producers))
                for producer in evt_producers:
                    producer.submit_producer_message(
                        topic, _id, self.queue, *args, **kwargs)
            elif msg_kind == 'reply':
                uuid = msg['uuid']

                if uuid not in self.pending_responses:
                    continue

                pending_status = self.pending_responses[uuid]
                cur_time = time.time()
                init_time = pending_status['emit_time']
                ttl = pending_status['ttl']
                missing = pending_status['missing']

                if (cur_time - init_time) * 1000 > ttl:
                    self.pending_responses.pop(uuid)
                else:
                    response = msg['args']
                    topic = msg['topic']
                    evt_result_listeners = self.evt_result_listeners.get(
                        topic, set({}))
                    for listener in evt_result_listeners:
                        listener.send_result(topic, *response)
                missing -= 1
                pending_status['missing'] = missing
                if missing == 0:
                    self.pending_responses.pop(uuid, None)

    def stop(self):
        """
        Stop the dispatcher.

        Recursively stop the dispatcher as well as the registered
        listeners/result producers.
        """
        msg = QueueMsg(kind='exit', topic=None, args=tuple(),
                       kwargs={}, reply_to=None)
        self.queue.put(msg)

    def register_result_listener(self, listener: ResultListener, topic: str):
        """
        Register a result listener on a given topic.

        Parameters
        ----------
        listener: ResultListener
            The listener to register on the given `topic`.
        topic: str
            The identifier of the topic to listen results on.
        """
        topic_listeners = self.evt_result_listeners.get(topic, set({}))
        topic_listeners |= {listener}
        self.evt_result_listeners[topic] = topic_listeners

    def deregister_result_listener(self, listener: ResultListener, topic: str):
        """
        Deregister a result listener on a given topic.

        Parameters
        ----------
        listener: ResultListener
            The result listener to deregister.
        topic: str
            The topic on which the result listener was registered.
        """
        topic_listeners = self.evt_result_listeners.get(topic, set({}))
        topic_listeners -= {listener}
        self.evt_result_listeners[topic] = topic_listeners

    def register_result_producer(self, producer: Producer, topic: str):
        """
        Register a result producer on a given topic.

        Parameters
        ----------
        producer: Producer
            The producer to register on the given `topic`.
        topic: str
            The identifier of the topic to produce results on.
        """
        producers = self.evt_producers.get(topic, set({}))
        producers |= {producer}
        self.evt_producers[topic] = producers

    def deregister_result_producer(self, producer: Producer, topic: str):
        """
        Deregister a result producer on a given topic.

        Parameters
        ----------
        producer: Producer
            The producer to deregister.
        topic: str
            The topic on which the producer was registered.
        """
        producers = self.evt_producers.get(topic, set({}))
        producers -= {producer}
        self.evt_producers[topic] = producers

    def send_request(self, topic: str, *args, ttl: float = 5000, **kwargs):
        """
        Send a request to all result producers registered on a given topic.

        Parameters
        ----------
        topic: str
            The identifier of the topic to request results on.
        args: tuple
            Positional arguments to pass to the call.
        ttl: float
            Maximum timeout to obtain responses.
        kwargs: dict
            Optional arguments dictionary to pass to the call.

        Notes
        -----
        The responses will be dispatched to the listeners registered on the
        given topic.
        """
        kwargs['ttl'] = ttl
        msg = QueueMsg(kind='request', topic=topic, args=args, kwargs=kwargs,
                       uuid=None, reply_to=None)
        self.queue.put(msg)
