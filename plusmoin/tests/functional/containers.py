#!/usr/bin/env python
import os
import sys
import time
import json
import logging
import docker


class BuildFailure(Exception):
    """Exception raised when failing to build a container"""
    pass


class DockerContainers(object):
    """ Class used to build, start and stop the test docker containers

    Args:
        root (str): Root path containing the folder for the docker images
        containers (list): List of container definitions of the form: {
                               'image': <docker image name>,
                               'name': <docker container name>,
                               'ports': {
                                   <container port>: <host port>,
                                   ...
                                },
                                'links': {
                                    <container name>: <alias>,
                                    ...
                                 }
                          }
        base_url (str): Docker base url
        version (str): Docker version
 
   """
    def __init__(self, root, containers, base_url='unix://var/run/docker.sock', version='1.14'):
        self.root = root
        self.containers = {}
        for c in containers:
            self.containers[c['name']] = {
                'image': c['image'],
                'container': None,
                'status': None,
                'links': c['links'],
                'ports': c['ports']
            }
        self.docker = docker.Client(base_url=base_url, version=version)

    def build(self):
        """ Build all the images and create containers

        Raises:
            BuildFailure: On build errors
        """
        logger = logging.getLogger('containers')
        for name in self.containers:
            image = self.containers[name]['image']
            logger.info('Building image {}'.format(image))
            stream = self.docker.build(path=os.path.join(self.root, image), tag=image)
            for line in stream:
                info = json.loads(line)
                if 'error' in info:
                    logger.error("Failed building image {}".format(image))
                    logger.error("Error: {}".format(info['error']))
                    raise BuildFailure()
            logger.info('Creating container {} from image {}'.format(name, image))
            result = self.docker.create_container(
                image=image,
                detach=True,
                ports=self.containers[name]['ports'].values(),
                name=name
            )
            if 'Id' not in result:
                logger.error('Failed to create container {}'.format(name))
                raise BuildFailure()
            self.containers[name]['container'] = result['Id']
            self.containers[name]['status'] = 'stopped'
                
    def start(self):
        """ Start all the containers"""
        for name in self.containers:
            self.start_container(name)
            # Give time for each server to start, as they may depend on each
            # other.
            time.sleep(2)

    def start_container(self, name):
        """ Start the container

        Args:
            name (str): The name of the container
        """
        if self.containers[name]['status'] != 'stopped':
            return

        logger = logging.getLogger('containers')
        logger.info("Starting container {}".format(name))
        self.docker.start(
            container=self.containers[name]['container'],
            port_bindings=self.containers[name]['ports'], 
            links=self.containers[name]['links'],
        )
        self.containers[name]['status'] = 'started'

    def stop(self):
        """ Stop all containers"""
        for c in self.containers:
            self.stop_container(c)

    def stop_container(self, name):
        """ Stop the container

        Args:
            name (str): Name of the container to stop
        """
        if self.containers[name]['status'] == 'paused':
            self.unpause_container(name)
        if self.containers[name]['status'] != 'started':
            return

        logger = logging.getLogger('containers')
        logger.info('Stoping container {}'.format(name))
        self.docker.stop(container=self.containers[name]['container'])
        self.containers[name]['status'] = 'stopped'

    def remove(self):
        """ Remove all containers """
        for c in self.containers:
            self.remove_container(c)

    def remove_container(self, name):
        """ Remove the container build

        Args:
            name (str): Name of the of the container to remove
        """
        if self.containers[name]['status'] != 'stopped':
            self.stop_container(name)
        if self.containers[name]['status'] != 'stopped':
            return

        logger = logging.getLogger('containers')
        logger.info('Removing container {}'.format(name))
        self.docker.remove_container(container=self.containers[name]['container'])
        self.containers[name]['status'] = None

    def pause(self):
        """ Pause all containers """
        for c in self.containers:
            self.pause_container(c)

    def pause_container(self, name):
        """ Pause the container

        Args:
            name (str): Name of the of the container to pause
        """
        if self.containers[name]['status'] != 'started':
            return

        logger = logging.getLogger('containers')
        logger.info('Pausing container {}'.format(name))
        self.docker.pause(container=self.containers[name]['container'])
        self.containers[name]['status'] = 'paused'

    def unpause(self):
        """ Unpause all containers """
        for c in self.containers:
            self.unpause_container(c)

    def unpause_container(self, name):
        """ Unpause the container

        Args:
            name (str): Name of the of the container to unpause
        """
        if self.containers[name]['status'] != 'paused':
            return

        logger = logging.getLogger('containers')
        logger.info('Unpausing container {}'.format(name))
        self.docker.unpause(container=self.containers[name]['container'])
        self.containers[name]['status'] = 'started'

