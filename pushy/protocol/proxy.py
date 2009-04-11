# Copyright (c) 2008, 2009 Andrew Wilkins <axwalk@gmail.com>
# 
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

from pushy.protocol.message import message_types
import pushy.util
import types


class ProxyType:
    def __init__(self, code, name):
        self.code = code
        self.name = name
    def __repr__(self):
        return "ProxyType(%d, '%s')" % (self.code, self.name)
    def __str__(self):
        return self.name
    def __int__(self):
        return self.code
    def __eq__(self, other):
        if type(other) is int: return other == self.code
        elif type(other) is str: return other == self.name
        return other.__class__ is ProxyType and other.code == self.code

    @staticmethod
    def get(obj):
        if isinstance(obj, StopIteration):
            return ProxyType.stopiteration
        if isinstance(obj, AttributeError):
            return ProxyType.attributeerror
        if isinstance(obj, Exception):
            return ProxyType.exception
        if isinstance(obj, dict):
            return (ProxyType.dictionary, obj.keys())
        if isinstance(obj, types.ModuleType):
            return ProxyType.module
        return ProxyType.object


def get_opmask(obj):
    mask = 0L
    for t in message_types:
        if t.name.startswith("op__"):
            if hasattr(obj, t.name[2:]):
                mask = mask + 1
            mask <<= 1
    return (mask >> 1)


def Proxy(id_, opmask, proxy_type, args, conn):
    """
    Create a proxy object, which delegates attribute access and method
    invocation to an object in a remote Python interpreter.
    """

    # Determine the class to use for the proxy type.
    if proxy_type == ProxyType.stopiteration:
        class StopIterationProxy(StopIteration, object):
            def __getattribute__(self, name): return conn.getattr(id_, name)
        ProxyClass = StopIterationProxy
    elif proxy_type == ProxyType.attributeerror:
        class AttributeErrorProxy(AttributeError, object):
            def __getattribute__(self, name): return conn.getattr(id_, name)
        ProxyClass = AttributeErrorProxy
    elif proxy_type == ProxyType.exception:
        class ExceptionProxy(Exception, object):
            def __getattribute__(self, name): return conn.getattr(id_, name)
        ProxyClass = ExceptionProxy
    elif proxy_type == ProxyType.dictionary:
        pushy.util.logger.info("Got a dictionary type (%r)", args)
        class DictionaryProxy(dict):
            def __init__(self):
                if args is not None:
                    dict.__init__(self, zip(args, [None]*len(args)))
                else:
                    dict.__init__(self)
            def __getattribute__(self, name):
                pushy.util.logger.info("DictionaryProxy.getattr(%s)", name)
                return conn.getattr(id_, name)
        ProxyClass = DictionaryProxy
    elif proxy_type == ProxyType.module:
        pushy.util.logger.info("Got a module type")
        class ModuleProxy(types.ModuleType):
            def __init__(self): types.ModuleType.__init__(self, "")
            def __getattribute__(self, name):
                pushy.util.logger.info("ModuleProxy.getattr(%s)", name)
                return conn.getattr(id_, name)
        ProxyClass = ModuleProxy
    else:
        class ObjectProxy(object):
            def __getattribute__(self, name):
                pushy.util.logger.info("getattr(%s)", name)
                return conn.getattr(id_, name)
        ProxyClass = ObjectProxy

    # Callable for delegating to an operator on the remote object.
    class Operator:
        def __init__(self, type_):
            self.type_ = type_
        def __call__(self, *args, **kwargs):
            return conn.operator(self.type_, id_, args, kwargs)

    # Create proxy operators.
    op_index = -1
    while opmask:
        if opmask & 1:
            type_ = message_types[op_index]
            method = Operator(type_)
            setattr(ProxyClass, type_.name[2:], method)
        opmask >>= 1
        op_index -= 1

    # Add __str__ and __repr__ methods
    #def method(self):
    #    return conn.getstr(id_)
    #setattr(ProxyClass, "__str__", method)
    #def method(self):
    #    return conn.getrepr(id_)
    #setattr(ProxyClass, "__repr__", method)

    # Make sure we support the iteration protocol properly
    #if hasattr(ProxyClass, "__iter__"):
    def method(self):
        return conn.getattr(id_, "next")()
    setattr(ProxyClass, "next", method)

    def method(self, name, value):
        return conn.setattr(id_, name, value)
    setattr(ProxyClass, "__setattr__", method)

    return ProxyClass()

###############################################################################
# Create enumeration of proxy types
###############################################################################

proxy_names = (
  "object",
  "exception",
  "stopiteration",
  "attributeerror",
  "dictionary",
  "module"
)
proxy_types = []
for i,t in enumerate(proxy_names):
    p = ProxyType(i, t)
    proxy_types.append(p)
    setattr(ProxyType, t, p)

