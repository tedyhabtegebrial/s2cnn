# pylint: disable=R,C,E1101
import torch
import numpy as np
from functools import lru_cache


def so3_ft(x, b, grid):
    """
    Perform a discrete SO(3) Fourier transform of a signal with local support.

    :param x: an array of signals on SO(3), shape (..., n_spatial) where n_spatial is the number of non-zeros.
     Note: the signal is assumed to be real.
    :param b: bandwidth of the transform
    :param grid: list of (alpha, beta, gamma) triplets
    :return x_hat: an array of spectral signals, shape (..., n_spectral, 2) where n_spectral is the number of spectral
     coefficients for a bandwidth-b transform. The last axis stores real and imaginary parts.
    """
    # F is the local Fourier matrix, shape (n_spatial, 2 * n_spectral)
    F = setup_so3_ft(b, grid, device_type=x.device.type, device_index=x.device.index)

    # Get sizes
    sz = x.size()                                  # shape (..., n_spatial)
    n_spatial = sz[-1]
    n_spectral = F.size()[-1] // 2
    assert F.size()[-1] % 2 == 0, 'F should be a complex array with the real and imaginary parts coalesced.'
    assert n_spatial == F.size()[0], "Last dim of x should have length n_spatial = %i for chosen grid." % F.size()[0]

    # Flatten first few dimensions of x
    x_mat = x.view(-1, n_spatial)                  # shape (N, n_spatial)

    # Do the actual computation
    result = torch.mm(x_mat, F)                    # shape (N, 2 * n_spectral)

    # Unfold the leading dimensions and the complex dim
    result = result.view(*sz[:-1], n_spectral, 2)  # shape (..., n_spectral, 2)

    return result


@lru_cache(maxsize=32)
def setup_so3_ft(b, grid, device_type, device_index):
    from lie_learn.representations.SO3.wigner_d import wigner_D_matrix

    # Note: optionally get quadrature weights for the chosen grid and use them to weigh the D matrices below.
    # This is optional because we can also view the filter coefficients as having absorbed the weights already.
    # The weights depend on the spacing between the point of the grid
    # Only the coefficient sin(beta) can be added without requireing to know the spacings

    # Sample the Wigner-D functions on the local grid
    n_spatial = len(grid)
    n_spectral = np.sum([(2 * l + 1) ** 2 for l in range(b)])
    F = np.zeros((n_spatial, n_spectral), dtype=complex)
    for i in range(n_spatial):
        Dmats = [wigner_D_matrix(l, grid[i][0], grid[i][1], grid[i][2],
                                 field='complex', normalization='quantum', order='centered', condon_shortley='cs')
                 .conj()
                 for l in range(b)]
        F[i] = np.hstack([Dl.flatten() for Dl in Dmats])

    # F is a complex matrix of shape (n_spatial, n_spectral)
    # If we view it as float, we get a real matrix of shape (n_spatial, 2 * n_spectral)
    # In the so3_local_ft, we will multiply a batch of real (..., n_spatial) vectors x with this matrix F as xF.
    # The result is a (..., 2 * n_spectral) array that can be interpreted as a batch of complex vectors.
    F = F.view('float')

    # convert to torch Tensor
    F = torch.tensor(F.astype(np.float32), dtype=torch.float32, device=torch.device(device_type, device_index))  # pylint: disable=E1102

    return F
