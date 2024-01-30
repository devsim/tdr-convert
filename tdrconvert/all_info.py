from . import load_devsim as ds
from . import read_tdr
import numpy as np

class PhysicalGroup:
    def __init__(self, dim, name, index):
        self.dim = dim
        self.name = name
        self.index = index
        etype = -1
        if dim == 0:
            etype = 15 # 1-node point
        elif dim == 1:
            etype = 1 # 2-node line
        elif dim == 2:
            etype = 2 # 3-node triangle
        elif dim == 3:
            etype = 4 # 4-node tetrahedron
        self.etype = etype

class RegionInfo:
    def __init__(self, node_to_coordinates, elements, transform_elements):
        self.node_to_coordinates = node_to_coordinates
        if transform_elements:
            self.elements = transform_nodes_to_coordinates(node_to_coordinates, elements)
        else:
            # 1 based indexing for gmsh, tetgen, exodus
            self.elements = elements[:] + 1

class BoundaryInfo:
    def __init__(self, node_to_coordinates, elements, transform_elements):
        self.node_to_coordinates = node_to_coordinates
        if transform_elements:
            self.elements = elements
        else:
            # 1 based indexing for gmsh, tetgen, exodus
            self.elements = elements[:] + 1

def transform_nodes_to_coordinates(node_to_coordinates, elements):
    out_elements = [None] * len(elements)
    for i, e in enumerate(elements):
        # GMSH is a 1 based system
        # TODO: see if numpy can do this faster
        out_elements[i] = tuple([node_to_coordinates[j] + 1 for j in e])
    return out_elements

def get_physical_groups(device):
    regions = ds.get_region_list(device=device)
    contacts = ds.get_contact_list(device=device)
    interfaces = ds.get_interface_list(device=device)
    dim = ds.get_dimension(device=device)

    groups = {}
    index = 1
    for c in contacts:
        groups[c] = PhysicalGroup(dim=dim-1, name=c, index=index)
        index += 1
    for i in interfaces:
        groups[i] = PhysicalGroup(dim=dim-1, name=i, index=index)
        index += 1
    for r in regions:
        groups[r] = PhysicalGroup(dim=dim, name=r, index=index)
        index += 1

    return groups

def get_region_info(device):
    #
    # using devsim
    #
    region_info = {}
    max_coordinate = -1
    regions = ds.get_region_list(device=device)

    for region in regions:
        node_to_coordinates = [int(i) for i in ds.get_node_model_values(device=device, region=region, name="coordinate_index")]
        elements = ds.get_element_node_list(device=device, region=region, reorder=True)
        region_info[region] = RegionInfo(node_to_coordinates=node_to_coordinates, elements=elements, transform_elements=True)

    return region_info

def get_boundary_info(device, region_info):
    #
    # using devsim
    #
    contacts = ds.get_contact_list(device=device)
    interfaces = ds.get_interface_list(device=device)

    boundary_info = {}
    for contact in contacts:
        region = ds.get_region_list(device=device, contact=contact)[0]
        elements = ds.get_element_node_list(device=device, region=region, contact=contact, reorder=True)
        boundary_info[contact] = BoundaryInfo(node_to_coordinates=region_info[region].node_to_coordinates, elements=elements, transform_elements=True)

    for interface in interfaces:
        region = ds.get_region_list(device=device, interface=interface)[0]
        elements = ds.get_element_node_list(device=device, region=region, interface=interface,reorder=True)
        boundary_info[interface] = BoundaryInfo(node_to_coordinates=region_info[region].node_to_coordinates, elements=elements, transform_elements=True)
    return boundary_info

def get_coordinates(device, region_info):
    #
    # using devsim
    #
    contacts = ds.get_contact_list(device=device)
    regions = ds.get_region_list(device=device)

    max_coordinate = -1
    for region in region_info.values():
        region_max_coordinate = max(region.node_to_coordinates)
        max_coordinate = max(max_coordinate, region_max_coordinate)

    coordinates = [None] * (max_coordinate + 1)

    # collection of coordinates
    axis_names = ['x', 'y', 'z']
    for region in regions:
        node_coordinates = region_info[region].node_to_coordinates
        axis = []
        for i in axis_names:
            axis.append(ds.get_node_model_values(device=device, region=region, name=i))

        axis_values = list(zip(*axis))
        for ic, rc in enumerate(node_coordinates):
            coordinates[rc] = axis_values[ic]

    return coordinates


def get_device_info(device):
    #
    # using devsim
    #
    contacts = ds.get_contact_list(device=device)
    device_info = {}
    contact_info = {}
    region_info = {}
    interface_info = {}

    for c in ds.get_contact_list(device=device):
        region = ds.get_region_list(device=device, contact=c)[0]
        material = ds.get_material(device=device, contact=c)
        contact_info[c] = {
            'name'     : c,
            'region'   : region,
            'material' : material,
        }

    for i in ds.get_interface_list(device=device):
        region = ds.get_region_list(device=device, interface=i)
        interface_info[i] = {
            'name'     : i,
            'region0'   : region[0],
            'region1'   : region[1],
        }

    for r in ds.get_region_list(device=device):
        material = ds.get_material(device=device, region=r)
        region_info[r] = {
            'name'     : r,
            'material'   : material,
        }

    device_info = {
        'name': device,
        'regions': region_info,
        'contacts': contact_info,
        'interfaces': interface_info,
        'dimension': ds.get_dimension(device=device),
    }
    return device_info

def get_all_info(device):
    #
    # using devsim
    #
    contacts = ds.get_contact_list(device=device)
    groups = get_physical_groups(device=device)
    region_info = get_region_info(device=device)
    boundary_info = get_boundary_info(device=device, region_info=region_info)
    coordinates = get_coordinates(device=device, region_info=region_info)
    device_info = get_device_info(device=device)

    all_info = {
        'groups': groups,
        'region_info': region_info,
        'boundary_info': boundary_info,
        'coordinates': coordinates,
        'device_info': device_info,
    }

    return all_info

def get_tdr_device_info(device, data):
    device_info = {}
    contact_info = {}
    region_info = {}
    interface_info = {}

    for r in data['regions']:
        name = r['name']
        typename = r['typename']
        if typename == 'contact':
            contact_info[name] = {
                'name'     : name,
                'region' : data['regions'][r['bulk 0']]['name'],
                'material' : r['material'],
            }
        elif typename == 'interface':
            interface_info[name] = {
                'name'     : name,
                'region0'  : data['regions'][r['bulk 0']]['name'],
                'region1'  : data['regions'][r['bulk 1']]['name'],
            }
        elif typename == 'region':
            region_info[name] = {
                'name'     : name,
                'material' : r['material'],
            }

    device_info = {
        'name': device,
        'regions': region_info,
        'contacts': contact_info,
        'interfaces': interface_info,
        'dimension': data['dimension'],
    }
    return device_info



def get_info_from_tdr_data(device, data):
    print("Collecting TDR data")
    #
    # groups
    #
    dim = data['dimension']
    #contacts = ds.get_contact_list(device=device)
    #interfaces = ds.get_interface_list(device=device)
    #dim = ds.get_dimension(device=device)
    groups = {}
    index = 1
    for r in data['regions']:
        name = r['name']
        # TODO: worry about name conflicts later
        if r['typename'] in ('contact', 'interface'):
            groups[name] = PhysicalGroup(dim=dim-1, name=name, index=index)
        else:
            groups[name] = PhysicalGroup(dim=dim, name=name, index=index)
        index += 1

    region_info = {}
    vname = read_tdr.get_shape_name(dim)
    for r in data['regions']:
        if r['typename'] == 'region':
            e =r['elements']
            region_info[r['name']] = RegionInfo(node_to_coordinates=None, elements=e[vname], transform_elements=False)

    boundary_info = {}

    sname = read_tdr.get_shape_name(dim-1)
    for r in data['regions']:
        if r['typename'] in ('contact', 'interface'):
            e =r['elements']
            boundary_info[r['name']] = BoundaryInfo(node_to_coordinates=None, elements=e[sname], transform_elements=False)

    coordinates = data['coordinates']
    coordinates = coordinates.reshape(-1, 3)

    all_info = {
        'coordinates' : coordinates,
        'groups' : groups,
        'region_info' : region_info,
        'boundary_info' : boundary_info,
        'device_info' : get_tdr_device_info(device, data),
    }
    return all_info

