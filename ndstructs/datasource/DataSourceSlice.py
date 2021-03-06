from ndstructs.datasource.DataSource import DataSource, AddressMode
from ndstructs import Slice5D, Shape5D, Array5D, Point5D
from ndstructs.point5D import SLC_PARAM
from typing import Iterator, Optional


class DataSourceSlice(Slice5D):
    def __init__(
        self,
        datasource: DataSource,
        *,
        t: Optional[SLC_PARAM] = None,
        c: Optional[SLC_PARAM] = None,
        x: Optional[SLC_PARAM] = None,
        y: Optional[SLC_PARAM] = None,
        z: Optional[SLC_PARAM] = None,
    ):
        super().__init__(
            t=t if t is not None else datasource.roi.t,
            c=c if c is not None else datasource.roi.c,
            x=x if x is not None else datasource.roi.x,
            y=y if y is not None else datasource.roi.y,
            z=z if z is not None else datasource.roi.z,
        )
        self.datasource = datasource

    def with_coord(
        self,
        *,
        t: Optional[SLC_PARAM] = None,
        c: Optional[SLC_PARAM] = None,
        x: Optional[SLC_PARAM] = None,
        y: Optional[SLC_PARAM] = None,
        z: Optional[SLC_PARAM] = None,
    ) -> "DataSourceSlice":
        slc = self.roi.with_coord(t=t, c=c, x=x, y=y, z=z)
        return self.__class__(datasource=self.datasource, **slc.to_dict())

    def defined(self) -> "DataSourceSlice":
        return self.defined_with(self.full_shape)

    def __repr__(self) -> str:
        return super().__repr__() + " " + self.datasource.url

    def full(self) -> "DataSourceSlice":
        return self.with_coord(**self.full_shape.to_slice_5d().to_dict())

    @property
    def full_shape(self) -> Shape5D:
        return self.datasource.shape

    def contains(self, slc: Slice5D) -> bool:
        return super().contains(slc.defined_with(self.full_shape))

    @property
    def tile_shape(self) -> Shape5D:
        return self.datasource.tile_shape

    @property
    def dtype(self):
        return self.datasource.dtype

    def is_tile(self, tile_shape: Shape5D = None) -> bool:
        tile_shape = tile_shape or self.tile_shape
        has_tile_start = self.start % tile_shape == Point5D.zero()
        has_tile_end = self.stop % tile_shape == Point5D.zero() or self.stop == self.full().stop
        return has_tile_start and has_tile_end

    @property
    def roi(self) -> Slice5D:
        return Slice5D(t=self.t, c=self.c, x=self.x, y=self.y, z=self.z)

    def retrieve(self, address_mode: AddressMode = AddressMode.BLACK) -> Array5D:
        return self.datasource.retrieve(self.roi, address_mode=address_mode)

    def split(self, block_shape: Optional[Shape5D] = None) -> Iterator["DataSourceSlice"]:
        if not self.is_defined():
            return self.defined().split(block_shape=block_shape)
        yield from super().split(block_shape or self.tile_shape)

    def get_tiles(self, tile_shape: Shape5D = None, clamp: bool = True) -> Iterator["DataSourceSlice"]:
        if not self.is_defined():
            return self.defined().get_tiles(tile_shape=tile_shape, clamp=clamp)
        for tile in super().get_tiles(tile_shape or self.tile_shape):
            if clamp:
                clamped = tile.clamped(self)
                if not self.contains(clamped):
                    continue
                yield clamped
            else:
                yield tile

    def get_neighboring_tiles(self, tile_shape: Shape5D = None) -> Iterator["DataSourceSlice"]:
        if not self.is_defined():
            return self.defined().get_neighboring_tiles(tile_shape=tile_shape)
        tile_shape = tile_shape or self.tile_shape
        assert self.is_tile(tile_shape)
        for axis in Point5D.LABELS:
            for axis_offset in (tile_shape[axis], -tile_shape[axis]):
                offset = Point5D.zero(**{axis: axis_offset})
                neighbor = self.translated(offset).clamped(self.full())
                if neighbor.shape.hypervolume > 0 and neighbor != self:
                    yield neighbor
