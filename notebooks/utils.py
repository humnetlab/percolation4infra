# Standard Libraries
import os
import json
import csv
from datetime import datetime, timedelta
import warnings

# Data Manipulation
import pandas as pd
import numpy as np
import geopandas as gpd

# Visualization
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import seaborn as sns
from contextily import add_basemap
from folium.plugins import TimeSliderChoropleth
import folium
import contextily as ctx
from pyproj import Transformer

# Geometry and Spatial Analysis
import shapely
from shapely.ops import polygonize

# Graph and Network Analysis
import networkx as nx
import igraph

# Utilities
import itertools
from itertools import count
from mycolorpy import colorlist as mcp

# Specialized Libraries
import momepy

import glob
import os
from PIL import Image

# Configure Settings
sns.set_theme(style="white")
warnings.filterwarnings("ignore")

def process_subgraph(G, condition):
    """Helper function to process subgraphs (congested or non-congested)."""
    sub_nodes = [u for u in G.nodes if G.nodes[u].get("congest") == condition]
    subgraph = G.subgraph(sub_nodes)
    sizes = [len(c) for c in sorted(nx.connected_components(subgraph), key=len, reverse=True)]
    subgraphs = [list(c) for c in sorted(nx.connected_components(subgraph), key=len, reverse=True)]
    return subgraphs, sizes

def check_bottleneck(G, edge1, edge2, threshold, plot=True):
    bottleneck = []
    candidates = list(set(edge2).difference(set(edge1)))
    for candidate in candidates:
        
        selected_nodes = [
            [u, v] for u, v, k, e in G.edges(data=True, keys=True)
            if e['name'] in set([candidate])
        ]
        
        selected_nodes = set([x for sublist in selected_nodes for x in sublist])
        
        edges_to_move = [
            e['name'] for u, v, k, e in G.edges(data=True, keys=True)
            if u in selected_nodes or v in selected_nodes
        ]
        
        selected_edges = [
            (u, v, k) for u, v, k, e in G.edges(data=True, keys=True)
            if e['name'] in list(set(edge2).difference(set(edges_to_move)))
        ]
        
        G_selected = G.edge_subgraph(selected_edges)
        
        largest_component_size = len(sorted(nx.connected_components(G_selected), key=len, reverse=True)[0])
        
        if largest_component_size / len(edge2) < threshold:
            bottleneck.append(candidate)
        
    return bottleneck

class LoadData:
    def __init__(self):
        self.G_primal = None
        self.G_dual = None
        
    def load_map_data(self, section_path, nodes_path):
        # Load and preprocess data
        section = gpd.read_file(section_path)
        nodes = gpd.read_file(nodes_path)

        # Add geometric properties to the section data
        section['length'] = section.geometry.length
        section['near_start'] = shapely.get_point(section['geometry'], 0)
        section['near_end'] = shapely.get_point(section['geometry'], -1)
        section['original_middle'] = section['geometry'].centroid

        # Prepare GeoDataFrames for merging
        section_middle = gpd.GeoDataFrame(
            section[['id', 'original_middle']].rename(columns={'id': 'edge_id', 'original_middle': 'middle_geometry'})
        )[['edge_id', 'middle_geometry']]

        section_end = gpd.GeoDataFrame(section[['id', 'near_end']].rename(columns={'near_end': 'geometry'}))
        section_end = section_end.sjoin_nearest(nodes, how='left', max_distance=30).rename(
            columns={'geometry': 'original_end_geometry', 'id_right': 'near_end_node'}
        )[['near_end_node', 'original_end_geometry']]

        section_start = gpd.GeoDataFrame(section[['id', 'near_start']].rename(columns={'near_start': 'geometry'}))
        section_start = section_start.sjoin_nearest(nodes, how='left', max_distance=30).rename(
            columns={'geometry': 'original_start_geometry', 'id_right': 'near_start_node'}
        )[['near_start_node', 'original_start_geometry']]

        # Combine data into a single DataFrame
        col_names = [
            'edge_id', 'middle_geometry', 'near_start_node', 'near_end_node',
            'original_start_geometry', 'original_end_geometry',
            'near_start_geometry', 'near_end_geometry'
        ]
        df = (
            pd.concat([section_middle, section_start, section_end], axis=1)
            .merge(nodes, left_on='near_start_node', right_on='id', how='left')
            .merge(nodes, left_on='near_end_node', right_on='id', how='left')
            .rename(columns={'geometry_x': 'near_start_geometry', 'geometry_y': 'near_end_geometry'})[col_names]
        )

        # Initialize graph structures
        node_section = {}
        G_primal = nx.MultiGraph()

        # Build the primal graph
        for _, row in df.iterrows():
            # Determine start node
            if row['near_start_node'] > 0:
                start = int(row['near_start_node'])
                loc_s = row['near_start_geometry']
            else:
                start = f"{int(row['edge_id'])}s"
                loc_s = row['original_start_geometry']

            # Determine end node
            if row['near_end_node'] > 0:
                end = int(row['near_end_node'])
                loc_e = row['near_end_geometry']
            else:
                end = f"{int(row['edge_id'])}e"
                loc_e = row['original_end_geometry']

            # Handle self-loops
            if end == start:
                end = f"{int(row['edge_id'])}d"
                loc_e = row['original_end_geometry']

            # Add nodes and edges to the primal graph
            G_primal.add_node(start, loc=loc_s)
            G_primal.add_node(end, loc=loc_e)
            G_primal.add_edge(start, end, name=int(row['edge_id']))

            # Track edge mappings
            if (start, end) not in node_section:
                node_section[(start, end)] = [int(row['edge_id'])]
            else:
                node_section[(start, end)].append(int(row['edge_id']))

        # Build the dual graph
        G_dual = nx.line_graph(G_primal)

        # Relabel nodes in the dual graph
        mapping = {}
        for u in G_dual.nodes():
            start = u[0]; end = u[1]
            try:
                mapping[u] = node_section[(start, end)][0]
            except:
                mapping[u] = node_section[(end, start)][0]
            try:
                node_section[(start, end)] = node_section[(start, end)][1:]
            except:
                node_section[(end, start)] = node_section[(end, start)][1:]

        G_dual = nx.relabel_nodes(G_dual, mapping)
        
        self.G_primal = G_primal
        self.G_dual = G_dual
        return G_primal, G_dual

    
    def load_aimsun_data(self, plan_name, i):

        def process_mis_data(table_path):
            """Helper function to process MISECT and MISECTIEM data."""
            mis = pd.read_csv(table_path)
            mis = mis[(mis['ent'] != 0)&(mis['sid'] == 0)]
            mis = mis.mask(mis < 0, np.nan) 
            return mis

        # Process MISECT and MISECTIEM data
        misect = process_mis_data('../data/raw/'+plan_name+'_'+str(i)+'.csv')
        attr = ['oid', 'speed', 'density', 'flow', 'ent', 'ttime']
        misect_attr = (
            misect[attr]
            .sort_values(by=['oid', 'ent'])
            [['oid', 'speed', 'density', 'ttime', 'flow', 'ent']]
        )
        
        misectiem = process_mis_data('../data/raw/'+plan_name+'_'+'emi'+'_'+str(i)+'.csv')
        attr = ['oid', 'ent', 'CO2_interurban', 'NOx_interurban', 'VOC_interurban', 'PM_interurban']
        misectiem_attr = (
            misectiem[attr]
            .sort_values(by=['oid', 'ent'])
            [['oid', 'ent', 'CO2_interurban', 'NOx_interurban', 'VOC_interurban', 'PM_interurban']]
        )
        
        data = misect_attr.merge(misectiem_attr, on=['oid', 'ent'], how='left')
        
        # Calculate congestion and emission
        total = []
        for oid, group in data.groupby('oid'):
            max_flow = group['flow'].max()
            density_thres = group[group['flow'] == max_flow]['density'].values[0]
            group['if_congest'] = (group['density'] > density_thres).astype(int)
            total.append(group)
        total = pd.concat(total)

        return total
    
    def load_aimsun_metrics(self, total):
        # Initialize metrics
        mfd, density, speed, traveltime = [], [], [], []
        co2, nox, voc, pm = [], [], [], []

        # Process congestion and non-congestion metrics
        for ent in np.sort(total['ent'].unique()):
            total_ent = total[total['ent'] == ent]

            # Aggregate metrics
            mfd.append(total_ent['flow'].mean())
            density.append(total_ent['density'].mean())
            speed.append(total_ent['speed'].mean())
            traveltime.append(total_ent['ttime'].mean())
            
            co2.append(total_ent['CO2_interurban'].mean())
            nox.append(total_ent['NOx_interurban'].mean())
            voc.append(total_ent['VOC_interurban'].mean())
            pm.append(total_ent['PM_interurban'].mean())

        return mfd, density, speed, traveltime, co2, nox, voc, pm
        
    def calculate_time_series(self,total):
        # Initialize metrics
        l_g, s_g, n_c = [], [], []

        # Process congestion and non-congestion metrics
        for ent in np.sort(total['ent'].unique()):
            total_ent = total[total['ent'] == ent]
            G = self.G_dual.copy()

            # Update graph nodes with congestion data
            for _, row in total_ent.iterrows():
                try:
                    G.nodes[int(row['oid'])].update({
                        "congest": row['if_congest']
                    })
                except KeyError:
                    continue

            def process_subgraph(G, condition):
                """Helper function to process subgraphs (congested or non-congested)."""
                sub_nodes = [u for u in G.nodes if G.nodes[u].get("congest") == condition]
                subgraph = G.subgraph(sub_nodes)
                sizes = [len(c) for c in sorted(nx.connected_components(subgraph), key=len, reverse=True)]
                return subgraph, sizes

            # Process congested subgraph
            G_congest, sizes = process_subgraph(G, condition=1)
            l_g.append(sizes[0] if sizes else 0)
            s_g.append(sizes[1] if len(sizes) > 1 else 0)
            n_c.append(len(sizes))
        
        return l_g, s_g, n_c
    
    def calculate_percolation_time(self, l_g, s_g, interval = 60, method='l'):
        if method=='s':
            percolation_time = np.argmax(s_g)
        else:
            percolation_time = np.argmax(l_g[interval:]- np.array(l_g[:-interval]))
        return percolation_time
    
    def calculate_critical_locations(self, total, critical_time, threshold):

        # Process each time step
        times, sections, sizes = [], [], []
        
        for ent in np.sort(total['ent'].unique()):
            total_ent = total[total.ent == ent]
            G = self.G_dual.copy()

            # Update graph nodes with traffic data
            for _, row in total_ent.iterrows():
                start = int(row['oid'])
                try:
                    G.nodes[start].update({
                        "congest": row['if_congest'],
                        "flow": row['flow'],
                        "density": row['density'],
                        "speed": row['speed']
                    })
                except KeyError:
                    continue
            
            cg_subgraph, cg_sizes = process_subgraph(G, condition=1)
            for i in range(len(cg_subgraph)):
                sections.append(cg_subgraph[i])
                sizes.append(cg_sizes[i])
                times.append(ent)

        congest_loc = pd.DataFrame({'section': sections, 'sizes': sizes, 'time': times}).sort_values(by='time')
        
        # Get the nodes for ent1
        list2d = list(congest_loc[congest_loc['time'] == critical_time].sort_values(by=['sizes'], ascending=False).section.values)
        selected_nodes1 = list(itertools.chain(*list2d))

        # Get the nodes for ent2
        interval = 5
        selected_nodes2 = congest_loc[congest_loc['time'] == critical_time+interval].sort_values(by=['sizes'], ascending=False).section.values[0]

        # Compute the bottleneck
        critical_loc = check_bottleneck(self.G_primal, selected_nodes1, selected_nodes2, threshold)
        
        # find edges in g_primal with edge equal to 28802
        intersection = [
            [u, v] for u, v, k, e in self.G_primal.edges(data=True, keys=True)
            if e['name'] in critical_loc
        ]
        intersection = set(item for sublist in intersection for item in sublist if 'd' not in str(item) and 'e' not in str(item) and 's' not in str(item))

        # # Convert the list to a string with space-separated values
        # content = ' '.join(map(str, intersection))

        # # Write the string to a text file
        # with open("../result/intersections/bottleneck_"+str(plan_name)+".txt", "w") as file:
        #     file.write(content)
        
        return critical_loc,intersection        

        
        
    