import yaml
import sys

def get_clients_config(n_clients):
    result = {}
    for i in range(1, n_clients + 1):
        result[f'client{i}'] = {
            'container_name': f'client{i}',
            'image': 'client:latest',
            'entrypoint': '/client',
            'environment': [
                f'CLI_ID={i}',
                'CLI_SERVER_ADDRESS=server:12345',
            ],
            'networks': [
                'testing_net'
            ],
            'depends_on': [
                'server'
            ],
            'volumes':[
                './client/config.yaml:/config.yaml:ro'
            ]
        }
    return result

def generate_yaml(output_file, n_clients):
    server_config = {
        'container_name': 'server',
        'image': 'server:latest',
        'entrypoint': 'python3 /main.py',
        'environment': [
            'PYTHONUNBUFFERED=1',
        ],
        'networks': [
            'testing_net'
        ],
        'volumes':[
            './server/config.ini:/config.ini:ro'
        ]
}

    networks_config = {
        'testing_net': {
            'name': 'tp0_testing_net', 
            'driver': 'bridge', 
            'ipam': {
                'driver': 'default',
                'config': [{'subnet': '172.25.125.0/24'}]
            }
        }
    }

    compose_dict = {
        'name': 'tp0',
        'services': {
            'server': server_config,
            **get_clients_config(n_clients)
        },
        'networks': networks_config
    }

    with open(output_file, 'w') as f:
        yaml.dump(compose_dict, f, default_flow_style=False, sort_keys=False)

if __name__ == "__main__":
    archivo_salida = sys.argv[1]
    cantidad_clientes = int(sys.argv[2])
    
    generate_yaml(archivo_salida, cantidad_clientes)