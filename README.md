# nutils-SI

Part of the [Nutils](http://www.nutils.org) suite of numerical utilities, the
SI module provides a framework for working with physical units in Python. It
has no dependencies beyond Python itself, yet is fully inter-operable with
Numpy's API as well as Nutils' own function arrays.


## Installation

The SI module is most conveniently installed using Python's pip installer:

    python -m pip install nutils-SI

Alternatively the package can be installed from source by calling `python -m
pip install .` (note the dot) from inside the source directory.

The module will be installed in the nutils namespace, alongside other
components of the Nutils suite, from where it should be imortable as `SI`:

    >>> from nutils import SI


## Usage

The SI module defines all base units and derived units of the International
System of Units (SI) plus an Angle dimension, as well as the full set of metric
prefixes. Dimensional values are generated primarily by parsing a string value.

    >>> v = SI.parse('7μN*5h/6g')

The parser recognizes the multiplication (\*) and division (/) operators to
separate factors. Every factor can be prefixed with a scale and suffixed with a
power. The remainder must be either a unit, or else a unit with a metric
prefix.

In this example, the resulting object is of type "L/T", i.e. length over time,
which is a subtype of Quantity that stores the powers L=1 and T=-1. Many
subtypes are readily defined by their physical names; others can be created
through manipulation.

    >>> type(v) == SI.Velocity == SI.Length / SI.Time
    True

While `parse` can instantiate any subtype of Quantity, we could have created
the same object by instantiating Velocity directly, which has the advantage of
verifying that the specified quantity is indeed of the desired dimension.

    >>> w = SI.Velocity('8km')
    Traceback (most recent call last):
         ...
    TypeError: expected [L/T], got [L]

Explicit subtypes can also be used in function annotations:

    >>> def f(size: SI.Length, load: SI.Force): pass

The Quantity types act as an opaque container. As long as a quantity has a
physical dimension, its value is inaccessible. The value can only be retrieved
by dividing out a reference quantity, so that the result becomes dimensionless
and the Quantity wrapper falls away.

    >>> v / SI.parse('m/s')
    21.0

To simplify the fairly common situation that the reference quantity is a unit
or another parsed value, any operation involving a Quantity and a string is
handled by parsing the latter automatically.

    >>> v / 'm/s'
    21.0

A value can also be retrieved as textual output via string formatting. The
syntax is similar to that of floating point values, with the desired unit
taking the place of the 'f' suffix.

    >>> f'velocity: {v:.1m/s}'
    'velocity: 21.0m/s'

A Quantity container can hold an object of any type that supports arithmetical
manipulation. Though an object can technically be wrapped directly, the
idiomatic way is to rely on multiplication so as not to depend on the specifics
of the internal reference system.

    >>> import numpy
    >>> F = numpy.array([1,2,3]) * SI.parse('N')

For convenience, Quantity objects define the shape, ndim and size attributes.
Beyond this, however, no Numpy specific methods or attributes are defined.
Array manipulations must be performed via Numpy's API, which is supported via
the array protocol ([NEP
18](https://numpy.org/neps/nep-0018-array-function-protocol.html)).

    >>> f'total force: {numpy.sum(F):.1N}'
    'total force: 6.0N'


## Extension

In case the predefined set of dimensions and units are insufficient, both can
be extended. For instance, though it is not part of the official SI system, it
might be desirable to add an angular dimension. This is done by creating a new
Dimension instance, using a symbol that avoids the existing symbols T, L, M, I,
Θ, N, J and A:

    >>> Xonon = SI.Dimension.create('X')

At this point, the dimension is not very useful yet as it lacks units. To
rectify this we define the unit yam as being internally represented by a unit
value:

    >>> SI.units.yam = Xonon.reference_quantity

Additional units can be defined by relating them to pre-existing ones. Here we
define the unit zop as the equal of 15 kilo-yam:

    >>> import math
    >>> SI.units.zop = 15 * SI.units.kyam

Alternatively, units can be defined using the same string syntax that is used
by the Quantity constructor. Nevertheless, the following statement fails as we
cannot define the same unit twice.

    >>> SI.units.zop = '15kyam'
    Traceback (most recent call last):
         ...
    ValueError: cannot define 'zop': unit is already defined

Having defined the new units we can directly use them:

    >>> SI.parse('24mzop/h')
    0.1[X/T]
