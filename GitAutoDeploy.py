#!/usr/bin/env python

import json, urlparse, sys, os, hashlib, hmac
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from subprocess import call

class GitAutoDeploy(BaseHTTPRequestHandler):

    CONFIG_FILEPATH = './GitAutoDeploy.conf.json'
    config = None
    quiet = False
    daemon = False

    @classmethod
    def getConfig(myClass):
        if(myClass.config == None):
            try:
                configString = open(myClass.CONFIG_FILEPATH).read()
            except:
                sys.exit('Could not load ' + myClass.CONFIG_FILEPATH + ' file')

            try:
                myClass.config = json.loads(configString)
            except:
                sys.exit(myClass.CONFIG_FILEPATH + ' file is not valid json')

            for repository in myClass.config['repositories']:
                if(not os.path.isdir(repository['path'])):
                    sys.exit('Directory ' + repository['path'] + ' not found')
                if(not os.path.isdir(repository['path'] + '/.git')):
                    sys.exit('Directory ' + repository['path'] + ' is not a Git repository')

        return myClass.config

    def do_POST(self):
        try:
            url_refs = self.parseRequest()
            for url, ref in url_refs:
                paths = self.getMatchingPaths(url, ref)
                for path in paths:
                    self.pull(path)
                    self.deploy(path)
            self.respond_success()
        except Exception as e:
            self.respond_failure(500)
            print e

    def parseRequest(self):
        length = int(self.headers.getheader('content-length'))
        xhub_signature = self.headers.getheader('X-Hub-Signature')[5:]
        body = self.rfile.read(length)
        post = urlparse.parse_qs(body)
        items = []
        if not self.validate(
            body, 
            self.getConfig().get('secret', ''), 
            xhub_signature):
            print "Invalid signature"
            self.respond_failure(403)
            return items

        for itemString in post['payload']:
            item = json.loads(itemString)
            items.append((item['repository']['url'], item['ref']))
        return items

    def validate(self, data, secret, signature):
        if not secret:
            return True
        hm = hmac.new(str(secret), str(data), hashlib.sha1)
        if hm.hexdigest() != signature:
            return False
        return True

    def getMatchingPaths(self, repoUrl, ref):
        res = []
        config = self.getConfig()
        for repository in config['repositories']:
            if (repository['url'] == repoUrl and 
                repository.get('ref', '') in ('', ref)):
                res.append(repository['path'])
        return res

    def respond_success(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    def respond_failure(self, error_code=500):
        self.send_response(error_code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()        

    def pull(self, path):
        if(not self.quiet):
            print "\nPost push request received"
            print 'Updating ' + path
        call(['cd "' + path + '" && git pull'], shell=True)

    def deploy(self, path):
        config = self.getConfig()
        for repository in config['repositories']:
            if(repository['path'] == path):
                if 'deploy' in repository:
                     if(not self.quiet):
                         print 'Executing deploy command'
                     call(['cd "' + path + '" && ' + repository['deploy']], shell=True)
                break

def main():
    try:
        server = None
        for arg in sys.argv: 
            if(arg == '-d' or arg == '--daemon-mode'):
                GitAutoDeploy.daemon = True
                GitAutoDeploy.quiet = True
            if(arg == '-q' or arg == '--quiet'):
                GitAutoDeploy.quiet = True
                
        if(GitAutoDeploy.daemon):
            pid = os.fork()
            if(pid != 0):
                sys.exit()
            os.setsid()

        if(not GitAutoDeploy.quiet):
            print 'Github Autodeploy Service v 0.1 started'
        else:
            print 'Github Autodeploy Service v 0.1 started in daemon mode'
             
        server = HTTPServer(('', GitAutoDeploy.getConfig()['port']), GitAutoDeploy)
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit) as e:
        if(e): # wtf, why is this creating a new line?
            print >> sys.stderr, e

        if(not server is None):
            server.socket.close()

        if(not GitAutoDeploy.quiet):
            print 'Goodbye'

if __name__ == '__main__':
     main()
