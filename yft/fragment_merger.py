from typing import Optional

from szio.gta5.cwxml import (
    Geometry,
    Shader,
    Fragment,
    PhysicsChild,
)


def get_all_frag_geoms(frag_xml: Fragment) -> list[Geometry]:
    """Get all Geometries in a Fragment including those in Physics children and Cloths drawables."""
    geoms = frag_xml.drawable.all_geoms

    for child in frag_xml.physics.lod1.children:
        geoms.extend(child.drawable.all_geoms)

    for cloth in frag_xml.cloths:
        geoms.extend(cloth.drawable.all_geoms)

    return geoms


class FragmentMerger:
    """Merge hi and non hi Fragments."""
    @property
    def phys_children(self) -> list[PhysicsChild]:
        return self.frag.physics.lod1.children

    @property
    def phys_children_hi(self) -> list[PhysicsChild]:
        return self.hi_frag.physics.lod1.children

    def __init__(self, frag: Fragment, hi_frag: Fragment) -> None:
        self.frag = frag
        self.hi_frag = hi_frag

        if len(self.phys_children) != len(self.phys_children_hi):
            raise ValueError(
                f"Cannot merge Fragments '{self.frag.name}' and '{self.hi_frag.name}': Both Fragments must have same number of children!")

    def merge(self) -> Fragment:
        shaders: list[Shader] = self.frag.drawable.shader_group.shaders
        hi_shaders: list[Shader] = self.hi_frag.drawable.shader_group.shaders

        shader_merger = FragShaderMerger(shaders, hi_shaders)
        merged_shaders = shader_merger.merge()

        self.frag.drawable.shader_group.shaders = merged_shaders

        shader_merger.update_geom_shader_inds(self.frag)
        shader_merger.update_hi_geom_shader_inds(self.hi_frag)

        self.frag.drawable.hi_models = self.hi_frag.drawable.drawable_models_high

        self.merge_hi_children()

        # NOTE: we don't merge Cloth drawables because they have the same mesh in hi and non-hi fragments

        return self.frag

    def merge_hi_children(self):
        """Merge the hi and non hi Drawables of each physics child."""
        for child, hi_child in zip(self.phys_children, self.phys_children_hi):
            drawable = child.drawable
            hi_drawable = hi_child.drawable

            if drawable.is_empty or hi_drawable.is_empty:
                continue

            drawable.hi_models = hi_drawable.drawable_models_high


class FragShaderMerger:
    """Merge shader groups of Fragment and hi Fragment."""

    def __init__(self, shaders: list[Shader], hi_shaders: list[Shader]) -> None:
        self.shaders = shaders
        self.hi_shaders = hi_shaders

        self.new_shader_inds: dict[int, int] = {}
        self.new_hi_shader_inds: dict[int, int] = {}
        self.merged_shaders: list[Shader] = []

    def merge(self):
        """Merge _hi.yft shader group into non hi shader group. Returns the merged shaders."""
        for i, shader in enumerate(self.shaders):
            self.new_shader_inds[i] = len(self.merged_shaders)
            self.merged_shaders.append(shader)

        for i, shader in enumerate(self.hi_shaders):
            if shader in self.merged_shaders:
                self.new_hi_shader_inds[i] = self.merged_shaders.index(shader)
            else:
                self.new_hi_shader_inds[i] = len(self.merged_shaders)
                self.merged_shaders.append(shader)

        return self.merged_shaders

    def update_geom_shader_inds(self, frag: Fragment):
        """Update shader indices in non hi Fragment to use indices from merged
        shader list."""
        geoms = get_all_frag_geoms(frag)

        for geom in geoms:
            geom.shader_index = self.new_shader_inds[geom.shader_index]

    def update_hi_geom_shader_inds(self, hi_frag: Fragment):
        """Update shader indices in hi Fragment to use indices from merged
        shader list."""
        geoms = get_all_frag_geoms(hi_frag)

        for geom in geoms:
            geom.shader_index = self.new_hi_shader_inds[geom.shader_index]
