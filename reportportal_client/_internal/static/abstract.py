#  Copyright (c) 2023 EPAM Systems
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License

"""This module provides base abstract class for RP request objects."""

from abc import ABCMeta as _ABCMeta
from abc import abstractmethod

__all__ = ["AbstractBaseClass", "abstractmethod"]


class AbstractBaseClass(_ABCMeta):
    """Metaclass for pure Interfacing.

    Being set as __metaclass__, forbids direct object creation from this
    class, allowing only inheritance. I.e.

    class Interface(object):
        __metaclass__ = AbstractBaseClass
    i = Interface() -> will raise TypeError

    meanwhile,

    class Implementation(Interface):
        pass
    i = Implementation() -> success
    """

    _abc_registry = set()

    def __call__(cls, *args, **kwargs):
        """Disable instantiation for the interface classes."""
        if cls.__name__ in AbstractBaseClass._abc_registry:
            raise TypeError(f'No instantiation allowed for Interface-Class "{cls.__name__}". Please inherit.')

        result = super(AbstractBaseClass, cls).__call__(*args, **kwargs)
        return result

    def __new__(mcs, name, bases, namespace):
        """Register instance of the implementation class."""
        class_ = super(AbstractBaseClass, mcs).__new__(mcs, name, bases, namespace)
        if namespace.get("__metaclass__") is AbstractBaseClass:
            mcs._abc_registry.add(name)
        return class_
