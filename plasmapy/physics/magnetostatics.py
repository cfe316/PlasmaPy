"""
Define MagneticStatics class to calculate common static magnetic fields
as first raised in issue #100.
"""

import abc
from astropy import units as u, constants
import numpy as np

from scipy.special import roots_legendre


class MagnetoStatics(abc.ABC):
    """Abstract class for all kinds of magnetic static fields"""

    @abc.abstractmethod
    def magnetic_field(self, p: u.m) -> u.T:
        """
        Calculate magnetic field generated by this wire at position `p`

        Parameters
        ----------
        p : `astropy.units.Quantity`
            three-dimensional position vector

        Returns
        -------
        B : `astropy.units.Quantity`
            magnetic field at the specified positon

        """


class MagneticDipole(MagnetoStatics):
    """
    Simple magnetic dipole - two nearby opposite point charges.

    Parameters
    ----------
    moment: `astropy.units.Quantity`
        Magnetic moment vector, in units of A * m^2
    p0: `astropy.units.Quantity`
        Position of the dipole
    """
    @u.quantity_input()
    def __init__(self, moment: u.A * u.m**2, p0: u.m):
        self.moment = moment.to(u.A*u.m*u.m).value
        self.p0 = p0.to(u.m).value

    def __repr__(self):
        return "{name}(moment={moment}, p0={p0})".format(
            name=self.__class__.__name__,
            moment=self.moment,
            p0=self.p0
        )

    def magnetic_field(self, p: u.m) -> u.T:
        r = p - self.p0
        m = self.moment
        B = constants.mu0.value/4/np.pi \
            * (3*r*np.dot(m, r)/np.linalg.norm(r)**5 - m/np.linalg.norm(r)**3)
        return B*u.T


class Wire(MagnetoStatics):
    """
    Abstract wire class for concrete wires to be inherited from.
    """
    pass


class GeneralWire(Wire):
    """
    General wire class described by its parametric vector equation

    Parameters
    ----------
    parametric_eq: Callable
        the parametric vector function of the curve in space, in unit m
        .. math::

            l: \mathbb{R}\rightarrow\mathbb{R}^3

    t1: float
        lower bound of the parameter, smaller than t2
    t2: float
        upper bound of the parameter, larger than t1
    current: `astropy.units.Quantity`
        electric current
    """
    @u.quantity_input()
    def __init__(self, parametric_eq,
                 t1,
                 t2,
                 current:
                 u.A):
        if callable(parametric_eq):
            self.parametric_eq = parametric_eq
        else:
            raise ValueError("Argument parametric_eq should be a callable")
        if t1 < t2:
            self.t1 = t1
            self.t2 = t2
        else:
            raise ValueError(f"t1={t1} is not smaller than t2={t2}")
        self.current = current.to(u.A).value

    def magnetic_field(self, p: u.m, n: int=1000) -> u.T:
        """

        Parameters
        ----------
        p : `astropy.units.Quantity`
            three-dimensional position vector
        n : int, optional
            Number of segments for Wire calculation
            (defaults to 1000)

        Returns
        -------
        B : `astropy.units.Quantity`
            magnetic field at the specified positon

        Notes
        -----
        For simplicity, we segment the wire into n equal pieces,
        and assume each segment is straight. Default n is 1000.

        .. math::
        \vec B
        \approx \frac{\mu_0 I}{4\pi} \sum_{i=1}^{n}
        \frac{[\vec l(t_{i}) - \vec l(t_{i-1})] \times
        \left[\vec p - \frac{\vec l(t_{i}) + \vec l(t_{i-1})}{2}\right]}
        {\left|\vec p - \frac{\vec l(t_{i}) + \vec l(t_{i-1})}{2}\right|^3},
        \quad \text{where}\, t_i = t_{\min}+i/n*(t_{\max}-t_{\min})
        """
        p1 = self.parametric_eq(self.t1)
        step = (self.t2 - self.t1) / n
        t = self.t1
        B = 0
        for i in range(n):
            t = t + step
            p2 = self.parametric_eq(t)
            dl = p2 - p1
            p1 = p2
            R = p - (p2 + p1) / 2
            B += np.cross(dl, R)/np.linalg.norm(R)**3
        B = B*constants.mu0.value/4/np.pi*self.current
        return B*u.T


class FiniteStraightWire(Wire):
    """
    Finite length straight wire class.
    p1 to p2 direction is the possitive current direction.

    Parameters
    ----------
    p1: `astropy.units.Quantity`
        three-dimensional Cartesian coordinate of one end of the straight wire
    p2: `astropy.units.Quantity`
        three-dimensional Cartesian coordinate of another end of the straight wire
    current: `astropy.units.Quantity`
        electric current
    """
    @u.quantity_input()
    def __init__(self, p1: u.m, p2: u.m, current: u.A):
        self.p1 = p1.to(u.m).value
        self.p2 = p2.to(u.m).value
        if np.all(p1 == p2):
            raise ValueError("p1, p2 should not be the same point.")
        self.current = current.to(u.A).value

    def __repr__(self):
        return "{name}(p1={p1}, p2={p2}, current={current})".format(
            name=self.__class__.__name__,
            p1=self.p1,
            p2=self.p2,
            current=self.current
        )

    def magnetic_field(self, p) -> u.T:
        """
        let :math:`P_f` be the foot of perpendicular, :math:`\theta_1`(:math:`\theta_2`) be the
        angles between :math:`\overrightarrow{PP_1}`(:math:`\overrightarrow{PP_2}`)
        and :math:`\overrightarrow{P_2P_1}`.

        .. math:
            \vec B = \frac{(\overrightarrow{P_2P_1}\times\overrightarrow{PP_f})^0}
                     {|\overrightarrow{PP_f}|}
                     \frac{\mu_0 I}{4\pi} (\cos\theta_1 - \cos\theta_2)

        """
        # foot of perpendicular
        p1, p2 = self.p1, self.p2
        p2_p1 = p2 - p1
        ratio = np.dot(p - p1, p2_p1)/np.dot(p2_p1, p2_p1)
        pf = p1 + p2_p1*ratio

        # angles: theta_1 = <p - p1, p2 - p1>, theta_2 = <p - p2, p2 - p1>
        cos_theta_1 = np.dot(p - p1, p2_p1)/np.linalg.norm(p - p1)/np.linalg.norm(p2_p1)
        cos_theta_2 = np.dot(p - p2, p2_p1)/np.linalg.norm(p - p2)/np.linalg.norm(p2_p1)

        B_unit = np.cross(p2_p1, p - pf)
        B_unit = B_unit/np.linalg.norm(B_unit)

        B = B_unit/np.linalg.norm(p-pf)*(cos_theta_1 - cos_theta_2) \
            * constants.mu0.value/4/np.pi*self.current

        return B*u.T

    def to_GeneralWire(self):
        p1, p2 = self.p1, self.p2
        return GeneralWire(lambda t: p1+(p2-p1)*t, 0, 1, self.current*u.A)


class InfiniteStraightWire(Wire):
    """
    Infinite straight wire class.

    Parameters
    ----------
    direction:
        three-dimensional direction vector of the wire, also the positive current direction
    p0: `astropy.units.Quantity`
        one point on the wire
    current: `astropy.units.Quantity`
        electric current
    """
    @u.quantity_input()
    def __init__(self, direction, p0: u.m, current: u.A):
        self.direction = direction/np.linalg.norm(direction)
        self.p0 = p0.to(u.m).value
        self.current = current.to(u.A).value

    def __repr__(self):
        return "{name}(direction={direction}, p0={p0}, current={current})".format(
            name=self.__class__.__name__,
            direction=self.direction,
            p0=self.p0,
            current=self.current
        )

    def magnetic_field(self, p) -> u.T:
        """
        .. math:
            \vec B = \frac{\mu_0 I}{2\pi r}*(\vec l^0\times \vec{PP_0})^0,
            \text{where}\, \vec l^0\, \text{is the unit vector of current direction},
            r\, \text{is the perpendicular distance between} P_0 \text{and the infinite wire}
        """
        r = np.cross(self.direction, p - self.p0)
        B_unit = r/np.linalg.norm(r)
        r = np.linalg.norm(r)

        return B_unit/r*constants.mu0.value/2/np.pi*self.current*u.T


class CircularWire(Wire):
    """
    Circular wire(coil) class

    Parameters
    ----------
    normal:
        three-dimensional normal vector of the circular coil
    center: `astropy.units.Quantity`
        three-dimensional position vector of the circular coil's center
    radius: `astropy.units.Quantity`
        radius of the circular coil
    current: `astropy.units.Quantity`
        electric current
    """
    @u.quantity_input()
    def __init__(self, normal, center: u.m, radius: u.m,
                 current: u.A, n=300):
        self.normal = normal/np.linalg.norm(normal)
        self.center = center.to(u.m).value
        if radius > 0:
            self.radius = radius.to(u.m).value
        else:
            raise ValueError("Radius should bu larger than 0")
        self.current = current.to(u.A).value

        # parametric equation
        # find other two axises in the disc plane
        z = np.array([0, 0, 1])
        axis_x = np.cross(z, self.normal)
        axis_y = np.cross(self.normal, axis_x)

        if np.linalg.norm(axis_x) == 0:
            axis_x = np.array([1, 0, 0])
            axis_y = np.array([0, 1, 0])
        else:
            axis_x = axis_x/np.linalg.norm(axis_x)
            axis_y = axis_y/np.linalg.norm(axis_y)

        self.axis_x = axis_x
        self.axis_y = axis_y

        def curve(t):
            if isinstance(t, np.ndarray):
                t = np.expand_dims(t, 0)
                axis_x_mat = np.expand_dims(axis_x, 1)
                axis_y_mat = np.expand_dims(axis_y, 1)
                return self.radius*(np.matmul(axis_x_mat, np.cos(t))
                                    + np.matmul(axis_y_mat, np.sin(t))) \
                    + np.expand_dims(self.center, 1)
            else:
                return self.radius*(np.cos(t)*axis_x + np.sin(t)*axis_y) + self.center
        self.curve = curve

        self.roots_legendre = roots_legendre(n)
        self.n = n

    def __repr__(self):
        return "{name}(normal={normal}, center={center}, \
radius={radius}, current={current})".format(
            name=self.__class__.__name__,
            normal=self.normal,
            center=self.center,
            radius=self.radius,
            current=self.current
        )

    """
    .. math:
        \vec B
        = \frac{\mu_0 I}{4\pi}
        \int \frac{d\vec l\times(\vec p - \vec l(t))}{|\vec p - \vec l(t)|^3}\\
        = \frac{\mu_0 I}{4\pi} \int_{-\pi}^{\pi} {(-r\sin\theta \hat x + r\cos\theta \hat y)}
        \times \frac{\vec p - \vec l(t)}{|\vec p - \vec l(t)|^3} d\theta

    We use n points Gauss-Legendre quadrature to compute the integral. The default n is 300.
    """
    def magnetic_field(self, p) -> u.T:
        x, w = self.roots_legendre
        t = x*np.pi
        pt = self.curve(t)
        dl = self.radius*(
            - np.matmul(np.expand_dims(self.axis_x, 1), np.expand_dims(np.sin(t), 0))
            + np.matmul(np.expand_dims(self.axis_y, 1), np.expand_dims(np.cos(t), 0)))  # (3, n)

        r = np.expand_dims(p, 1) - pt  # (3, n)
        r_norm_3 = np.linalg.norm(r, axis=0)**3
        ft = np.cross(dl, r, axisa=0, axisb=0)/np.expand_dims(r_norm_3, 1)  # (n, 3)

        return np.pi*np.matmul(np.expand_dims(w, 0), ft).squeeze(0) \
            * constants.mu0.value/4/np.pi*self.current*u.T

    def to_GeneralWire(self):
        return GeneralWire(self.curve, -np.pi, np.pi, self.current*u.A)
