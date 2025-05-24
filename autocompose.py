#!/usr/bin/env python3

# Original script by Red5d, with modifications.
# https://github.com/Red5d/docker-autocompose

import docker
import sys
import argparse
import os

try:
    import pyaml 
except ImportError:
    try:
        import ruamel.yaml as pyaml
    except ImportError:
        try:
            import yaml as pyaml 
        except ImportError:
            sys.stderr.write("Unable to import a YAML library. Please install pyyaml, ruamel.yaml, or pyaml.\n")
            sys.exit(1)

def generate_compose(client, containers_to_inspect, include_all_env_vars, include_default_volumes):
    """
    Generates docker-compose configuration for the specified containers.
    """
    compose_data = {'version': '3.8', 'services': {}}
    networks_to_create = {}
    volumes_to_create = {}
    sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Initializing. Containers to inspect: {containers_to_inspect}\n")


    for container_name_or_id in containers_to_inspect:
        sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Attempting to get container: {container_name_or_id}\n")
        try:
            container = client.containers.get(container_name_or_id)
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Successfully got container object for: {container_name_or_id}\n")
        except docker.errors.NotFound:
            sys.stderr.write(f"Warning: Container '{container_name_or_id}' not found. Skipping.\n")
            continue
        except docker.errors.APIError as e:
            sys.stderr.write(f"Warning: Error getting container '{container_name_or_id}': {e}. Skipping.\n")
            continue

        service_name = container.attrs['Name'].lstrip('/') 
        if not service_name: 
            service_name = container.short_id 
        sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Processing service_name: '{service_name}' for container ID: {container.id}\n")

        service = {}
        
        # Image
        try:
            img_attrs = container.attrs.get('Image')
            config_img = container.attrs.get('Config', {}).get('Image')
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Image Attrs='{img_attrs}', Config Image='{config_img}'\n")
            if img_attrs:
                img = client.images.get(img_attrs) # Use Image ID from attrs
                if img.tags:
                    service['image'] = img.tags[0]
                    sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Using image from tags: {service['image']}\n")
                elif config_img: # Fallback to image name from container's config if no tags
                    service['image'] = config_img
                    sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': No tags, using image from config: {service['image']}\n")
                else: 
                    sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Image object found but no tags and no config image name. This is unusual.\n")
                    service['image'] = img_attrs 
            elif config_img: 
                 service['image'] = config_img
                 sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Image ID from attrs missing, using image from config: {service['image']}\n")
            else:
                sys.stderr.write(f"Warning: Could not determine image for {service_name}. Both Image ID and Config.Image are missing.\n")

        except docker.errors.ImageNotFound:
            service['image'] = container.attrs.get('Config', {}).get('Image')
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Image ID not found, using image from config: {service['image']}\n")
        except Exception as e:
            sys.stderr.write(f"Warning: Could not determine image for {service_name}: {e}. Using config image name if available.\n")
            service['image'] = container.attrs.get('Config', {}).get('Image', 'unknown_image_due_to_error')


        # Command
        if container.attrs['Config']['Cmd']:
            service['command'] = " ".join(container.attrs['Config']['Cmd'])
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Command set to: {service['command']}\n")


        # Environment Variables
        excluded_keys_from_label = []
        container_labels = container.attrs.get('Config', {}).get('Labels', {})
        if container_labels and 'AUTOCOMPOSE_EXCLUDE' in container_labels:
            exclude_str = container_labels.get('AUTOCOMPOSE_EXCLUDE', '')
            if exclude_str:
                excluded_keys_from_label = [key.strip() for key in exclude_str.split(',') if key.strip()]
                sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}' - Parsed AUTOCOMPOSE_EXCLUDE label: {excluded_keys_from_label}\n")
        else:
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}' - No AUTOCOMPOSE_EXCLUDE label found or it's empty.\n")


        if container.attrs['Config']['Env']:
            service['environment'] = {}
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}' - Processing ENV VARS...\n")
            for env_var_str in container.attrs['Config']['Env']:
                key, value = "", None 
                has_value_assignment = "=" in env_var_str
                if has_value_assignment:
                    key, value = env_var_str.split("=", 1)
                else:
                    key = env_var_str 
                
                sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}' - ENV: Original='{env_var_str}', Parsed Key='{key}' (Type: {type(key)})\n")
                sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}' - Excluded keys from label: {excluded_keys_from_label} (Type of items: {[type(ek) for ek in excluded_keys_from_label]})\n")

                if not key: 
                    continue

                if key in excluded_keys_from_label:
                    sys.stderr.write(f"Info: Excluding ENV VAR '{key}' for service '{service_name}' due to AUTOCOMPOSE_EXCLUDE label.\n")
                    continue 

                if include_all_env_vars: 
                     service['environment'][key] = value
                elif has_value_assignment: 
                    service['environment'][key] = value
            if not service.get('environment'): 
                if 'environment' in service: del service['environment'] 
            elif service.get('environment'): 
                sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}' - Final ENV: {service['environment']}\n")
            else: 
                 if 'environment' in service: del service['environment']

        
        # Ports
        if container.attrs['NetworkSettings']['Ports']:
            service['ports'] = []
            for port, host_bindings in container.attrs['NetworkSettings']['Ports'].items():
                if host_bindings:
                    for binding in host_bindings:
                        host_ip_str = f"{binding['HostIp']}:" if binding.get('HostIp') and binding['HostIp'] != '0.0.0.0' else ""
                        service['ports'].append(f"{host_ip_str}{binding['HostPort']}:{port}")
                else: 
                    service['ports'].append(str(port))
            if service.get('ports'): 
                 sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Ports: {service['ports']}\n")


        # Volumes
        service_volumes = []
        if container.attrs['Mounts']:
            for mount in container.attrs['Mounts']:
                source = mount.get('Source') 
                target = mount.get('Target') 

                if not source or not target: 
                    sys.stderr.write(f"Warning: Skipping mount with missing Source or Target for service '{service_name}': {mount}\n")
                    continue

                volume_str = f"{source}:{target}"
                if not mount.get('RW', True): 
                    volume_str += ":ro"

                if mount.get('Type') == 'volume':
                    is_default_docker_volume = len(mount['Name']) == 64 and all(c in '0123456789abcdef' for c in mount['Name'])
                    if include_default_volumes or not is_default_docker_volume:
                        service_volumes.append(volume_str)
                        if mount['Name'] not in volumes_to_create and not os.path.exists(source):
                            volumes_to_create[mount['Name']] = {'external': False if not is_default_docker_volume else True}
                    else:
                        sys.stderr.write(f"Info: Skipping default Docker volume '{mount['Name']}' for service '{service_name}'.\n")
                elif mount.get('Type') == 'bind':
                    service_volumes.append(volume_str)
            if service_volumes:
                service['volumes'] = service_volumes
                sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Volumes: {service['volumes']}\n")


        # Networks
        if container.attrs['NetworkSettings']['Networks']:
            service_networks = {} 
            network_names = list(container.attrs['NetworkSettings']['Networks'].keys())
            is_only_default_bridge = False
            if len(network_names) == 1 and network_names[0] == 'bridge':
                try:
                    network_obj = client.networks.get('bridge')
                    if network_obj.attrs.get('Driver') == 'bridge' and \
                       not network_obj.attrs.get('Options') and \
                       not network_obj.attrs.get('Internal') and \
                       network_obj.attrs.get('Scope') == 'local':
                        is_only_default_bridge = True
                except docker.errors.NotFound:
                    pass 
            
            if not is_only_default_bridge:
                for net_name, net_config in container.attrs['NetworkSettings']['Networks'].items():
                    if net_name == 'bridge':
                        try:
                            network_obj = client.networks.get('bridge')
                            if network_obj.attrs.get('Driver') == 'bridge' and \
                               not network_obj.attrs.get('Options') and \
                               not network_obj.attrs.get('Internal') and \
                               network_obj.attrs.get('Scope') == 'local':
                                continue 
                        except docker.errors.NotFound:
                            pass 

                    service_networks[net_name] = {} 
                    if net_name not in networks_to_create:
                        try:
                            network_obj = client.networks.get(net_name)
                            if network_obj.attrs.get('Driver') != 'bridge': 
                                 networks_to_create[net_name] = {'driver': network_obj.attrs.get('Driver')} if network_obj.attrs.get('Driver') else {}
                        except docker.errors.NotFound:
                             networks_to_create[net_name] = {} 
            if service_networks: 
                service['networks'] = service_networks
                sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Networks: {service['networks']}\n")


        # Restart Policy
        if container.attrs['HostConfig']['RestartPolicy'] and container.attrs['HostConfig']['RestartPolicy']['Name']:
            policy = container.attrs['HostConfig']['RestartPolicy']['Name']
            if policy != 'no': 
                service['restart'] = policy
        
        if container.attrs['HostConfig'].get('Privileged'): service['privileged'] = True
        if container.attrs['Config'].get('User'): service['user'] = container.attrs['Config']['User']
        if container.attrs['HostConfig'].get('PidMode') and container.attrs['HostConfig']['PidMode'] != "": service['pid'] = container.attrs['HostConfig']['PidMode']
        if container.attrs['HostConfig'].get('UTSMode') and container.attrs['HostConfig']['UTSMode'] != "": service['uts'] = container.attrs['HostConfig']['UTSMode']
        if container.attrs['Config'].get('WorkingDir') and container.attrs['Config']['WorkingDir'] != "":
            service['working_dir'] = container.attrs['Config']['WorkingDir']
        if container.attrs['Config'].get('Entrypoint'):
            service['entrypoint'] = " ".join(container.attrs['Config']['Entrypoint']) 
        if container.attrs['HostConfig'].get('CapAdd'):
            service['cap_add'] = container.attrs['HostConfig']['CapAdd']
        if container.attrs['HostConfig'].get('CapDrop'):
            service['cap_drop'] = container.attrs['HostConfig']['CapDrop']
        if container.attrs['HostConfig'].get('Devices'):
            service['devices'] = [f"{d['PathOnHost']}:{d['PathInContainer']}:{d['CgroupPermissions']}" for d in container.attrs['HostConfig']['Devices']]
        
        if container.attrs['Config'].get('Labels'):
            service_labels = container.attrs['Config']['Labels'] # Get all labels
            if service_labels: # If there are any labels
                service['labels'] = service_labels # Add them all to the service
                sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service '{service_name}': Labels added: {service['labels']}\n")
        
        if service and service.get('image'): 
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Final service dict for '{service_name}': {service}\n")
            compose_data['services'][service_name] = service
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Assigned service '{service_name}' to compose_data.\n")
        else:
            sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Service dict for '{service_name}' was empty or missing image. Not adding to compose_data.\n")


    if networks_to_create:
        compose_data['networks'] = networks_to_create
    if volumes_to_create:
        compose_data['volumes'] = volumes_to_create
    
    sys.stderr.write(f"[DEBUG AUTOCOMPOSE] Final compose_data before return: {compose_data}\n")
    return compose_data

def main():
    parser = argparse.ArgumentParser(description="Generate a docker-compose.yml from running Docker container(s).")
    parser.add_argument("containers", metavar="CONTAINER", nargs='+', help="Name or ID of one or more containers to inspect.")
    parser.add_argument(
        "--full", "-f",
        action="store_true",
        dest="include_all_env_vars", 
        help="Include all environment variables (respects AUTOCOMPOSE_EXCLUDE label)." 
    )
    parser.add_argument(
        "--include-default-volumes",
        action="store_true",
        help="Include default Docker-created volumes (often long hex names) in the output."
    )
    args = parser.parse_args()

    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        sys.stderr.write(f"Error: Could not connect to Docker daemon. Is it running and accessible?\n{e}\n")
        sys.exit(1)

    compose_config = generate_compose(
        client, 
        args.containers, 
        args.include_all_env_vars, 
        args.include_default_volumes
    )
    
    class MyDumper(pyaml.Dumper):
        def increase_indent(self, flow=False, indentless=False):
            return super(MyDumper, self).increase_indent(flow, False)

    pyaml.dump(compose_config, sys.stdout, Dumper=MyDumper, default_flow_style=False, sort_keys=False)

if __name__ == "__main__":
    main()
