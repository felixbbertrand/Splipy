# -*- coding: utf-8 -*-

"""Handy utilities for creating volumes."""

from math import pi, sqrt
import numpy as np
from GeoMod import Surface, Volume, BSplineBasis
import GeoMod.SurfaceFactory as SurfaceFactory

__all__ = ['cube', 'revolve', 'cylinder', 'extrude', 'edge_surfaces']


def cube(size=1):
    """cube([size=1])

    Create a cube with parmetric origin at *(0,0,0)*.

    :param size: Size(s), either a single scalar or a tuple of scalars per axis
    :type size: float or (float)
    :return: A linear parametrized box
    :rtype: Volume
    """
    result = Volume()
    result.scale(size)
    return result


def revolve(surf, theta=2 * pi):
    """revolve(surf, [theta=2pi])

    Revolve a volume by sweeping a surface in a rotational fashion around the
    *z* axis.

    :param Surface surf: Surface to revolve
    :param float theta: Angle to revolve, in radians
    :return: The revolved surface
    :rtype: Volume
    """
    surf = surf.clone()  # clone input surface, throw away old reference
    surf.set_dimension(3)  # add z-components (if not already present)
    surf.force_rational()  # add weight (if not already present)
    n = len(surf)  # number of control points of the surface
    cp = np.zeros((8 * n, 4))
    basis = BSplineBasis(3, [-1, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5], periodic=0)
    basis *= 2 * pi / 4  # set parametric domain to (0,2pi) in w-direction

    # loop around the circle and set control points by the traditional 9-point
    # circle curve with weights 1/sqrt(2), only here C0-periodic, so 8 points
    for i in range(8):
        if i % 2 == 0:
            weight = 1.0
        else:
            weight = 1.0 / sqrt(2)
        cp[i * n:(i + 1) * n, :] = np.reshape(surf.controlpoints.transpose(1, 0, 2), (n, 4))
        cp[i * n:(i + 1) * n, 2] *= weight
        cp[i * n:(i + 1) * n, 3] *= weight
        surf.rotate(pi / 4)
    return Volume(surf.bases[0], surf.bases[1], basis, cp, True)


def cylinder(r=1, h=1):
    """cylinder([r=1], [h=1])

    Create a solid cylinder with the *z* axis as central axis.

    :param float r: Radius
    :param float h: Height
    :return: The cylinder
    :rtype: Volume
    """
    shell = SurfaceFactory.cylinder(r, h)
    cp = []
    for controlpoint in shell:
        cp.append([0, 0, controlpoint[2], controlpoint[3]])  # project to z-axis
    for controlpoint in shell:
        cp.append(list(controlpoint))

    return Volume(shell.bases[0], shell.bases[1], BSplineBasis(), cp, True)


def extrude(surf, h):
    """Extrude a surface by sweeping it in the *z* direction to a given height.

    :param Surface surf: Surface to extrude
    :param float h: Height in the *z* direction
    :return: The extruded surface
    :rtype: Volume
    """
    surf.set_dimension(3)  # add z-components (if not already present)
    cp = []
    for controlpoint in surf:
        cp.append(list(controlpoint))
    surf += (0, 0, h)
    for controlpoint in surf:
        cp.append(list(controlpoint))
    surf -= (0, 0, h)
    return Volume(surf.bases[0], surf.bases[1], BSplineBasis(2), cp, surf.rational)


def edge_surfaces(*surfaces):
    """edge_surfaces(surfaces...)

    Create the volume defined by the region between the input surfaces.

    In case of six input surfaces, these must be given in the order: bottom,
    top, left, right, back, front. Opposing sides must be parametrized in the
    same directions.

    :param [Surface] surfaces: Two or six edge surfaces
    :return: The enclosed volume
    :rtype: Volume
    :raises ValueError: If the length of *surfaces* is not two or six
    """
    if len(surfaces) == 1: # probably gives input as a list-like single variable
        surfaces = surfaces[0]
    if len(surfaces) == 2:
        surf1 = surfaces[0].clone()
        surf2 = surfaces[1].clone()
        Surface.make_splines_identical(surf1, surf2)
        (n1, n2, d) = surf1.controlpoints.shape  # d = dimension + rational

        controlpoints = np.zeros((n1, n2, 2, d))
        controlpoints[:, :, 0, :] = surf1.controlpoints
        controlpoints[:, :, 1, :] = surf2.controlpoints

        # Volume constructor orders control points in a different way, so we
        # create it from scratch here
        result = Volume()
        result.bases = [surf1.bases[0], surf1.bases[1], BSplineBasis(2)]
        result.dimension = surf1.dimension
        result.rational = surf1.rational
        result.controlpoints = controlpoints

        return result
    elif len(surfaces) == 6:
        # coons patch (https://en.wikipedia.org/wiki/Coons_patch)
        umin = surfaces[0]
        umax = surfaces[1]
        vmin = surfaces[2]
        vmax = surfaces[3]
        wmin = surfaces[4]
        wmax = surfaces[5]
        vol1 = edge_surfaces(umin,umax)
        vol2 = edge_surfaces(vmin,vmax)
        vol3 = edge_surfaces(wmin,wmax)
        vol4 = Volume(controlpoints=vol1.corners(), rational=vol1.rational)
        vol1.swap(0, 2)
        vol1.swap(1, 2)
        vol2.swap(1, 2)
        vol4.swap(1, 2)
        Volume.make_splines_identical(vol1, vol2)
        Volume.make_splines_identical(vol1, vol3)
        Volume.make_splines_identical(vol1, vol4)
        Volume.make_splines_identical(vol2, vol3)
        Volume.make_splines_identical(vol2, vol4)
        Volume.make_splines_identical(vol3, vol4)
        result  = vol1.clone()
        result.controlpoints +=   vol2.controlpoints
        result.controlpoints +=   vol3.controlpoints
        result.controlpoints -= 2*vol4.controlpoints
        return result
    else:
        raise ValueError('Requires two or six input surfaces')

def loft(surfaces):
    # clone input, so we don't change those references
    # make sure everything has the same dimension since we need to compute length
    surfaces = [s.clone().set_dimension(3) for s in surfaces]
    if len(surfaces)==2:
        return SurfaceFactory.edge_curves(surfaces)
    elif len(surfaces)==3:
        # can't do cubic spline interpolation, so we'll do quadratic
        basis3 = BSplineBasis(3)
        dist  = basis3.greville()
    else:
        x = [s.center() for s in surfaces]

        # create knot vector from the euclidian length between the surfaces
        dist = [0]
        for (x1,x0) in zip(x[1:],x[:-1]):
            # disregard weight (coordinate 4), if it appears
            dist.append(dist[-1] + np.linalg.norm(x1[:3]-x0[:3]))

        # using "free" boundary condition by setting N'''(u) continuous at second to last and second knot
        knot = [dist[0]]*4 + dist[2:-2] + [dist[-1]]*4
        basis3 = BSplineBasis(4, knot)

    n = len(surfaces)
    for i in range(n):
        for j in range(i+1,n):
            Surface.make_splines_identical(surfaces[i], surfaces[j])

    basis1 = surfaces[0].bases[0]
    basis2 = surfaces[0].bases[1]
    m1     = basis1.num_functions()
    m2     = basis2.num_functions()
    dim    = len(surfaces[0][0])
    u      = basis1.greville() # parametric interpolation points
    v      = basis2.greville()
    w      = dist

    # compute matrices
    Nu     = basis1(u)
    Nv     = basis2(v)
    Nw     = basis3(w)
    Nu_inv = np.linalg.inv(Nu)
    Nv_inv = np.linalg.inv(Nv)
    Nw_inv = np.linalg.inv(Nw)

    # compute interpolation points in physical space
    x      = np.zeros((m1,m2,n, dim))
    for i in range(n):
        tmp        = np.tensordot(Nv, surfaces[i].controlpoints, axes=(1,1))
        x[:,:,i,:] = np.tensordot(Nu, tmp                      , axes=(1,1))

    # solve interpolation problem
    cp = np.tensordot(Nw_inv, x,  axes=(1,2))
    cp = np.tensordot(Nv_inv, cp, axes=(1,2))
    cp = np.tensordot(Nu_inv, cp, axes=(1,2))

    # re-order controlpoints so they match up with Surface constructor
    cp = np.reshape(cp.transpose((2, 1, 0, 3)), (m1*m2*n, dim))

    return Volume(basis1, basis2, basis3, cp, surfaces[0].rational)
