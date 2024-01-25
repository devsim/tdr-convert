from netCDF4 import Dataset,stringtoarr
import numpy as np

def write(rootgrp, all_info):
    print("writing exodus file")
    coordinates = all_info['coordinates']
    region_info = all_info['region_info']
    boundary_info = all_info['boundary_info']


    rootgrp.setncattr('api_version', np.array(8.03, 'f4'))
    rootgrp.setncattr('version', np.array(8.03, 'f4'))
    rootgrp.setncattr('floating_point_word_size', np.array(8, 'i4'))
    rootgrp.setncattr('file_size', np.array(1, 'i4'))
    rootgrp.setncattr('maximum_name_length', np.array(32, 'i4'))
    rootgrp.setncattr('int64_status', np.array(0, 'i4'))
    rootgrp.setncattr('title', 'tdrconvert')
    #
    # dimensions
    #
    len_name=256
    rootgrp.createDimension('len_name', len_name)
    rootgrp.createDimension('time_step', None)

    num_dim=all_info['device_info']['dimension']
    rootgrp.createDimension('num_dim', num_dim)
    rootgrp.createDimension('num_nodes', len(coordinates))

    elementcounts = [len(x.elements) for x in region_info.values()]
    nod_per_el = [len(x.elements[0]) for x in region_info.values()]
    rootgrp.createDimension('num_elem', sum(elementcounts))
    num_el_blk = len(elementcounts)
    rootgrp.createDimension('num_el_blk', num_el_blk)
#TODO: num_side_sets
    for n, c in enumerate(elementcounts):
       rootgrp.createDimension(f'num_el_in_blk{n+1}', c)
       rootgrp.createDimension(f'num_nod_per_el{n+1}', nod_per_el[n])
#side set stuff, include distribution factors
    rootgrp.createDimension('four', 4)
    len_string = 33
    rootgrp.createDimension('len_string', len_string)
    rootgrp.createDimension('num_qa_rec', 1)

    #
    # variables
    #
    x=rootgrp.createVariable('qa_records', 'S1', ('num_qa_rec', 'four', 'len_string'))
    x[0][0] = stringtoarr('tdrconvert', len_string)
    x[0][1] = stringtoarr('2024', len_string)
    x[0][2] = stringtoarr('01/25/2024', len_string)
    x[0][3] = stringtoarr('00:00:00', len_string)

    x=rootgrp.createVariable('time_whole', 'f8', ('time_step',))
    x[:]=0

    x=rootgrp.createVariable('eb_status', 'i4', ('num_el_blk',))
    x[:] = [1]*num_el_blk

    ebp=rootgrp.createVariable('eb_prop1', 'i4', ('num_el_blk',))
    # https://unidata.github.io/netcdf4-python/#attributes-in-a-netcdf-file
    # name is reserved in python
    ebp.setncattr('name', 'ID')
    for i in range(num_el_blk):
        ebp[i]=i+1



    #
    # coordinates
    #

    for i, n in enumerate(('coordx', 'coordy', 'coordz')):
        if i < num_dim:
            x = rootgrp.createVariable(n, 'f8', ('num_nodes',), compression='zlib')
            x[0:] = np.array([y[i] for y in coordinates])

    #
    # block names
    #

    ebn=rootgrp.createVariable('eb_names', 'S1', ('num_el_blk', 'len_name'), fill_value='')
    for i, x in enumerate(region_info.keys()):
        ebn[i] = stringtoarr(x, len_name)

    cn=rootgrp.createVariable('coor_names', 'S1', ('num_dim', 'len_name'), fill_value='')
    for i, x in enumerate(('x', 'y', 'z')):
        if i < num_dim:
            cn[i] = stringtoarr(x, len_name)

    #
    # connection data
    #
    for i,x in enumerate(region_info.values()):
        npe = nod_per_el[i]
        if npe == 3:
            sname = 'TRI3'
        elif npe == 4:
            sname = 'TETRA'
        s = str(i+1)
        cn=rootgrp.createVariable(f'connect{s}', 'i4', (f'num_el_in_blk{s}', f'num_nod_per_el{s}'))
        cn.elem_type = sname
        cn[:,:] = x.elements
    #
    # need to handle contacts as side sets
    #

#
# this is direct from tdr, may need a way to do this from devsim in the future
# write now we are only working in nodal data
#
def write_datasets_from_tdr(rootgrp, data):
    #print(data['datasets'])
    print("Merging TDR datasets")
    datasets = data['datasets']

    to_create = {}
    oindex = 0
    for i, d in enumerate(datasets):
        name = d['name']
        nrows = d['nrows']

        for j in range(nrows):
            if nrows == 1:
                oname = name
            else:
                oname = f'{name}_{j}'
            if oname not in to_create:
                to_create[oname] = {
                    'oindex' : oindex,
                    'dindex' : [],
                    'cindex' : j,
                }
                print(f'{oname} {oindex} {i} {j}')
                oindex += 1
            to_create[oname]['dindex'].append(i)

    num_nod_var = len(to_create)
    if num_nod_var == 0:
        print('no datasets to save into exodus')
        return
    rootgrp.createDimension('num_nod_var', num_nod_var)

    nv = rootgrp.createVariable('name_nod_var', 'S1', ('num_nod_var', 'len_name'))
    for k, v in to_create.items():
        #print(v)
        print(f'{v["oindex"]} {k} {len(k)} {num_nod_var} {len(to_create)}')
        nv[v['oindex']] = stringtoarr(k, rootgrp.dimensions['len_name'].size)

    num_nodes = rootgrp.dimensions['num_nodes'].size
    # Writing records
    temp_array = np.empty(num_nodes)
    for k, v in to_create.items():
        temp_array[:] = 0.0
        oi = v['oindex'] + 1
        #print(oi)
        vv = rootgrp.createVariable(f'vals_nod_var{oi}', 'f8', ('time_step', 'num_nodes'))

        ci = v['cindex']
        for di in v['dindex']:
            dataset = datasets[di]
            coordinate = data['regions'][dataset['region']]['elements']['coordinates']
            # does not handle coincident nodes in adjacent blocks
            #print(temp_array.shape)
            temp_array[coordinate] = dataset['values'][ci, :]
            #print(temp_array.shape)
            #print()
        vv[0,:] = temp_array

# make sure to handle nodal and element data
def write_exodus(filename, all_info, data):
    rootgrp = Dataset(filename, "w", format="NETCDF4")
    write(rootgrp, all_info)
    if 'datasets' in data:
        write_datasets_from_tdr(rootgrp, data)
    rootgrp.close()

