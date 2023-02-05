# Certification Authority for home use
For some use cases, self created SSL certificates are necessary. If you don't know why you need
such certificates, then most probably you don't need them. You should go ahead and use
e.g. Let's Encrypt.

If you know what you are doing, then this collection of scripts and config files helps in
operating a small home-use certification authority.

# Preconditions
The scripts are built for openssl. They were developed on a Mac, with openssl@1.1 installed via
homebrew. They should work fine on any Linux system, if you adapt the path to the openssl command
in the script. The scripts are not tested in Windows, but I suspect they work fine in WSL, e.g.
with Ubuntu.

# One-time setup

## Step one: Customize
Use `./init.sh`.  
This should open your default visual editor with the file `variables.sh` opened.
If this didn't work, open the file yourself with your editor of choice.  
Go through the entire file and set your desired values. After you are finished, I recommend to run `./cleanup.sh`
to get rid of any previous residues.  
Attention: `init` will reset your customized `variables.sh` file. 
Even worse: `cleanup` will delete all of your certificates! You have to start from scratch
afterwards.

## Step two: Create the certificates for the CA
Use `./generatecacerts.sh`.  
The password for the two private keys is asked only once. If you mistype, you won't realize it! 
I recommend to generate and store the passwords with a password manager, and then copy/paste it.  
After finishing, the certificates will be there:
* Root certificate: `rootca/certs/ca.cert.pem`
* Root private key: `rootca/private/ca.key.pem`
* Issuing certificate: `issuingca/certs/issuing.cert.pem`
* Issuing private key: `issuingca/private/issuing.key.pem`

Now would be a good time to run `backup.sh`.

# Issue server certificates
Server certificates are created with `generateservercert.sh <host>`. After creation, the files are here:
* Certificate: `issuingca/certs/`
* Private key: `issuingca/private/`

There will be an unencrypted key, because this is usually what you need on a server (e.g. on
a Synology DSM, or on a VMWare ESXi virtualizer). Make sure to delete the open keys after importing!
If you need to re-import later, use `decryptkey.sh` to create another open key.

# Renew server certificates
Server certificates are renewed with `renewservercert.sh <host>`. After renewal, the files are here:
* Certificate: `issuingca/certs/`
* Private key: `issuingca/private/`

There will be an unencrypted key, because this is usually what you need on a server (e.g. on
a Synology DSM, or on a VMWare ESXi virtualizer). Make sure to delete the open keys after importing!
If you need to re-import later, use `decryptkey.sh` to create another open key.

# References
A very big help was this document:
https://jamielinux.com/docs/openssl-certificate-authority/introduction.html

# TODO
* Sign a 3rd party CSR

# Extra scripts
* `test.sh`: Ignore this, it's used to test shell / script commands
* `decryptkey.sh`: Removes the encryption from a private key. This is often necessary when the key
has to be installed on a server
* `copyesxi.sh`: Copies the necessary certificates to a VMWare ESXi server into the correct directories
* `backup.sh`: This is the only bash script in the collection; It creates a zip file with all the
keys and certificates in it.
* `cleanup.sh`: Performs a complete reset; All certificates and keys will be deleted, including the
root CA. It's usually used during the test phase.
* `cleanup-clientcertsonly.sh`: Keeps the root/issuing CA intact, and cleans all certificates. I used
this when I changed the internal domain name, and needed to re-issue all of the server certificates.

# History
* &#x200B;19. October 2019: Initial version
* &#x200B;14. January 2022: Add certificate renewal

