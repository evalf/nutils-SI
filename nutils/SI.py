'''
Framework for working with physical units.

Part of the Nutils (http://www.nutils.org) suite of numerical utilities, the
nutils.SI module provides a framework for working with physical units. It has
no dependencies beyond Python itself, yet is fully inter-operable with Numpy's
API as well as Nutils' own function arrays.

For usage information see https://github.com/evalf/nutils-SI/.
'''

import fractions
import operator
import typing

__version__ = '0.1'


class Dimension(type):

    __cache = {} # subtypes

    @classmethod
    def create(mcls, arg):
        if not isinstance(arg, str):
            raise ValueError(f'create requires a string, got {type(arg).__name__}')
        if next(_split_factors(arg))[0] != arg:
            raise ValueError(f'invalid dimension string {arg!r}')
        if arg in mcls.__cache:
            raise ValueError(f'dimension {arg!r} is already in use')
        return mcls.from_powers({arg: fractions.Fraction(1)})

    @classmethod
    def from_powers(mcls, arg):
        if not isinstance(arg, dict):
            raise ValueError(f'from_powers requires a dict, got {type(arg).__name__}')
        if not all(isinstance(base, str) for base in arg.keys()):
            raise ValueError('all keys must be of type str')
        if not all(isinstance(power, fractions.Fraction) for power in arg.values()):
            raise ValueError('all values must be of type Fraction')
        powers = {base: power for base, power in arg.items() if power}
        name = ''.join(('*' if power > 0 else '/') + base
                     + (str(abs(power.numerator)) if abs(power.numerator) != 1 else '')
                     + ('_'+str(abs(power.denominator)) if abs(power.denominator) != 1 else '')
            for base, power in sorted(powers.items(), key=lambda item: item[::-1], reverse=True)).lstrip('*')
        try:
            cls = mcls.__cache[name]
        except KeyError:
            cls = mcls(f'[{name}]', (Quantity,), {})
            cls.__powers = powers
            cls.__qualname__ = 'Quantity.' + cls.__name__
            mcls.__cache[name] = cls
        return cls

    def __getattr__(cls, attr):
        if attr.startswith('[') and attr.endswith(']'):
            # this, together with __qualname__, is what makes pickle work
            return Dimension.from_powers({base: fractions.Fraction(power if isnumer else -power)
              for base, power, isnumer in _split_factors(attr[1:-1]) if power})
        raise AttributeError(attr)

    def __bool__(cls) -> bool:
        return bool(cls.__powers)

    def __or__(cls, other):
        return typing.Union[cls, other]

    def __ror__(cls, other):
        return typing.Union[other, cls]

    @staticmethod
    def _binop(op, a, b):
        return Dimension.from_powers({base: op(a.get(base, 0), b.get(base, 0)) for base in set(a) | set(b)})

    def __mul__(cls, other):
        if not isinstance(other, Dimension):
            return cls
        return cls._binop(operator.add, cls.__powers, other.__powers)

    def __rmul__(cls, other):
        assert not isinstance(other, Dimension)
        return cls

    def __truediv__(cls, other):
        if not isinstance(other, Dimension):
            return cls
        return cls._binop(operator.sub, cls.__powers, other.__powers)

    def __rtruediv__(cls, other):
        assert not isinstance(other, Dimension)
        return cls**-1

    def __pow__(cls, other):
        try:
            # Fraction supports only a fixed set of input types, so to extend
            # this we first see if we can convert the argument to integer.
            other = other.__index__()
        except:
            pass
        return Dimension.from_powers({base: power*fractions.Fraction(other) for base, power in cls.__powers.items()})

    def __stringly_loads__(cls, s):
        return cls(s)

    def __stringly_dumps__(cls, v):
        try:
            return v._parsed_from
        except AttributeError:
            raise NotImplementedError

    def __call__(cls, value):
        if cls is Quantity:
            raise Exception('Quantity base class cannot be instantiated')
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError(f'expected a str, got {type(value).__name__}')
        q = parse(value)
        expect = float if not cls.__powers else cls
        if type(q) != expect:
            raise TypeError(f'expected {expect.__name__}, got {type(q).__name__}')
        return q

    def __wrap__(cls, value):
        if not cls.__powers:
            return value
        return super().__call__(value)

    @property
    def reference_quantity(cls):
        return cls.__wrap__(1.)


def parse(s):
    if not isinstance(s, str):
        raise ValueError(f'expected a str, received {type(s).__name__}')
    tail = s.lstrip('+-0123456789.')
    q = float(s[:len(s)-len(tail)] or 1)
    for expr, power, isnumer in _split_factors(tail):
        u = expr.lstrip('+-0123456789.')
        try:
            v = float(expr[:len(expr)-len(u)] or 1) * getattr(units, u)**power
        except (ValueError, AttributeError):
            raise ValueError(f'invalid (sub)expression {expr!r}') from None
        q = q * v if isnumer else q / v
    q._parsed_from = s
    return q


class Quantity(metaclass=Dimension):

    def __init__(self, value):
        self.__value = value

    def __bool__(self):
        return bool(self.__value)

    def __len__(self):
        return len(self.__value)

    def __iter__(self):
        return map(type(self).__wrap__, self.__value)

    def __format__(self, format_spec):
        if not format_spec:
            return repr(self)
        n = len(format_spec) - len(format_spec.lstrip('0123456789.,'))
        v = self / type(self)(format_spec[n:])
        return v.__format__(format_spec[:n]+'f') + format_spec[n:]

    def __str__(self):
        return str(self.__value) + type(self).__name__

    @staticmethod
    def _dispatch(op, *args, **kwargs):
        name = op.__name__
        args = [parse(arg) if isinstance(arg, str) else arg for arg in args]
        if name in ('add', 'sub', 'subtract', 'hypot'):
            Dim = type(args[0])
            if type(args[1]) != Dim:
                raise TypeError(f'incompatible arguments for {name}: ' + ', '.join(type(arg).__name__ for arg in args))
        elif name in ('mul', 'multiply', 'matmul'):
            Dim = type(args[0]) * type(args[1])
        elif name in ('truediv', 'true_divide', 'divide'):
            Dim = type(args[0]) / type(args[1])
        elif name in ('neg', 'negative', 'pos', 'positive', 'abs', 'absolute', 'sum', 'mean', 'broadcast_to', 'transpose', 'trace', 'take', 'ptp', 'getitem', 'amax', 'amin', 'max', 'min'):
            Dim = type(args[0])
        elif name == 'sqrt':
            Dim = type(args[0])**fractions.Fraction(1,2)
        elif name == 'setitem':
            Dim = type(args[0])
            if type(args[2]) != Dim:
                raise TypeError(f'cannot assign {type(args[2]).__name__} to {Dim.__name__}')
        elif name in ('pow', 'power'):
            Dim = type(args[0])**args[1]
        elif name in ('lt', 'le', 'eq', 'ne', 'gt', 'ge', 'equal', 'not_equal', 'less', 'less_equal', 'greater', 'greater_equal', 'isfinite', 'isnan'):
            if any(type(q) != type(args[0]) for q in args[1:]):
                raise TypeError(f'incompatible arguments for {name}: ' + ', '.join(type(arg).__name__ for arg in args))
            Dim = Dimension.from_powers({})
        elif name in ('stack', 'concatenate'):
            stack_args, = args
            Dim = type(stack_args[0])
            if any(type(q) != Dim for q in stack_args[1:]):
                raise TypeError(f'incompatible arguments for {name}: ' + ', '.join(type(arg).__name__ for arg in stack_args))
            args = [q.__value for q in stack_args],
        elif name in ('shape', 'ndim', 'size'):
            Dim = Dimension.from_powers({})
        else:
            return NotImplemented
        assert isinstance(Dim, Dimension)
        return Dim.__wrap__(op(*(arg.__value if isinstance(arg, Quantity) else arg for arg in args), **kwargs))

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        if method != '__call__':
            return NotImplemented
        return self._dispatch(ufunc, *inputs, **kwargs)

    def __array_function__(self, func, types, args, kwargs):
        return self._dispatch(func, *args, **kwargs)

    __getitem__ = lambda self, item: self._dispatch(operator.getitem, self, item)
    __setitem__ = lambda self, item, value: self._dispatch(operator.setitem, self, item, value)

    def _unary(name):
        op = getattr(operator, name)
        return lambda self: self._dispatch(op, self)

    __neg__ = _unary('neg')
    __pos__ = _unary('pos')
    __abs__ = _unary('abs')

    def _binary(name):
        op = getattr(operator, name)
        return lambda self, other: self._dispatch(op, self, other)

    __lt__ = _binary('lt')
    __le__ = _binary('le')
    __eq__ = _binary('eq')
    __ne__ = _binary('ne')
    __gt__ = _binary('gt')
    __ge__ = _binary('ge')

    def _binary_r(name):
        op = getattr(operator, name)
        return lambda self, other: self._dispatch(op, self, other), \
               lambda self, other: self._dispatch(op, other, self)

    __add__, __radd__ = _binary_r('add')
    __sub__, __rsub__ = _binary_r('sub')
    __mul__, __rmul__ = _binary_r('mul')
    __matmul__, __rmatmul__ = _binary_r('matmul')
    __truediv__, __rtruediv__ = _binary_r('truediv')
    __mod__, __rmod__ = _binary_r('mod')
    __pow__, __rpow__ = _binary_r('pow')

    def _attr(name):
        return property(lambda self: getattr(self.__value, name))

    shape = _attr('shape')
    size = _attr('size')
    ndim = _attr('ndim')


class Units(dict):

    __prefix = dict(Y=1e24, Z=1e21, E=1e18, P=1e15, T=1e12, G=1e9, M=1e6, k=1e3, h=1e2,
        d=1e-1, c=1e-2, m=1e-3, μ=1e-6, n=1e-9, p=1e-12, f=1e-15, a=1e-18, z=1e-21, y=1e-24)

    def __setattr__(self, name, value):
        if not isinstance(value, Quantity):
            if not isinstance(value, str):
                raise TypeError(f'can only assign Quantity or str, got {type(value).__name__}')
            value = parse(value)
        if name in self:
            raise ValueError(f'cannot define {name!r}: unit is already defined')
        scaled_units = {p + name: value * s for p, s in self.__prefix.items()}
        collisions = set(scaled_units) & set(self)
        if collisions:
            raise ValueError(f'cannot define {name!r}: unit collides with ' + ', '.join(collisions))
        self[name] = value
        self.update(scaled_units)

    def __getattr__(self, name):
        if name not in self:
            raise AttributeError(name)
        return self[name]


def _split_factors(s):
    for parts in s.split('*'):
        isnumer = True
        for factor in parts.split('/'):
            if factor:
                base = factor.rstrip('0123456789_')
                numer, sep, denom = factor[len(base):].partition('_')
                power = fractions.Fraction(int(numer or 1), int(denom or 1))
                yield base, power, isnumer
            isnumer = False


## SI DIMENSIONS

Time = Dimension.create('T')
Length = Dimension.create('L')
Mass = Dimension.create('M')
ElectricCurrent = Dimension.create('I')
Temperature = Dimension.create('θ')
AmountOfSubstance = Dimension.create('N')
LuminousFlux = LuminousIntensity = Dimension.create('J')

Area = Length**2
Volume = Length**3
WaveNumber = Vergence = Length**-1
Velocity = Speed = Length / Time
Acceleration = Velocity / Time
Force = Weight = Mass * Acceleration
Pressure = Stress = Force / Area
Tension = Force / Length
Energy = Work = Heat = Force * Length
Power = Energy / Time
Density = Mass / Volume
SpecificVolume = MassConcentration = Density**-1
SurfaceDensity = Mass / Area
Viscosity = Pressure * Time
Frequency = Radioactivity = Time**-1
CurrentDensity = ElectricCurrent / Area
MagneticFieldStrength = ElectricCurrent / Length
Charge = ElectricCurrent * Time
ElectricPotential = Power / ElectricCurrent
Capacitance = Charge / ElectricPotential
Resistance = Impedance = Reactance = ElectricPotential / ElectricCurrent
Conductance = Resistance**-1
MagneticFlux = ElectricPotential * Time
MagneticFluxDensity = MagneticFlux / Area
Inductance = MagneticFlux / ElectricCurrent
Llluminance = LuminousFlux / Area
AbsorbedDose = EquivalentDose = Energy / Mass
Concentration = AmountOfSubstance / Volume
CatalyticActivity = AmountOfSubstance / Time


## SI UNITS

units = Units()

units.m = Length.reference_quantity
units.s = Time.reference_quantity
units.g = Mass.reference_quantity * 1e-3
units.A = ElectricCurrent.reference_quantity
units.K = Temperature.reference_quantity
units.mol = AmountOfSubstance.reference_quantity
units.cd = LuminousIntensity.reference_quantity

units.N = 'kg*m/s2' # newton
units.Pa = 'N/m2' # pascal
units.J = 'N*m' # joule
units.W = 'J/s' # watt
units.Hz = '/s' # hertz
units.C = 'A*s' # coulomb
units.V = 'J/C' # volt
units.F = 'C/V' # farad
units.Ω = 'V/A' # ohm
units.S = '/Ω' # siemens
units.Wb = 'V*s' # weber
units.T = 'Wb/m2' # tesla
units.H = 'Wb/A' # henry
units.lm = 'cd' # lumen
units.lx = 'lm/m2' # lux
units.Bq = '/s' # becquerel
units.Gy = 'J/kg' # gray
units.Sv = 'J/kg' # sievert
units.kat = 'mol/s' # katal

units.min = '60s' # minute
units.h = '60min' # hour
units.day = '24h' # day
units.au = '149597870700m' # astronomical unit
units.ha = 'hm2' # hectare
units.L = 'dm3' # liter
units.t = '1000kg' # ton
units.Da = '1.66053904020yg' # dalton
units.eV = '.1602176634aJ' # electronvolt
