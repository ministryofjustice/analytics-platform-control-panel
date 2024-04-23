#!/bin/sh

cat << EOF
This script assumes that you have been added to Github and AWS. You will also need access to 1password to get the shared .env file to set up environment variables
EOF

read -p "Are you sure you want to continue? <Y/N> " prompt
if [[ $prompt != "y" || $prompt != "Y" ]]; then
  exit 0
fi

# install homebrew if not already installed
if !brew --version; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo 'Skipping Homebrew. Already installed'
fi

# same with pyenv
if !pyenv --version; then
    brew install xz
    brew install pyenv
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
    echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
    echo 'eval "$(pyenv init -)"' >> ~/.zshrc
    source ~/.zshrc
    pyenv install 3.12.2
    pyenv global 3.12.2
else
    echo 'Skipping Pyenv. Already installed'
fi

# git secrets
brew install git-secrets
git secrets --register-aws --global
git secrets --install ~/.git-templates/git-secrets
git config --global init.templateDir ~/.git-templates/git-secrets

# control panel dependencies
brew install postgresql
brew services start postgres
brew services redis
brew services start redis
brew install npm
brew install kubectl
brew install helm
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
brew install awscli
brew install --cask aws-vault

source ~/.zshrc

cat << EOF
The next step will configure AWS single sign on.
This will create ~/.aws/config
This command will run 3 times as you will need to set this up for 3 regions
Enter the following for the 1st region

SSO session name (Recommended): dev 
SSO start URL [None]: https://moj.awsapps.com/start#/
SSO region [None]: eu-west-2  
SSO registration scopes [sso:account:access]: # keep default and just press enter

You will be taken to the aws console and asked if the boto client can be granted access to your data click allow, you should then see a confirmation box

you will then be shown a list of aws accounts to select. You can only select 1 option. You will be asked to supply some default configuration for the aws cli:

The first to select is analytical-platform-development

Then fill in the following options

CLI default client Region [None]: eu-west-1
CLI default output format [None]: json
CLI profile name [AdministratorAccess-xxxx]: admin-dev-sso

This will then create the profile for the development platform
EOF

read -p "Press enter to continue"

aws configure sso

cat << EOF
Enter the following for the 2nd region

SSO session name (Recommended): dev 

you will then be shown a list of aws accounts to select. You can only select 1 option. You will be asked to supply some default configuration for the aws cli:

The second to select is analytical-platform-production

Then fill in the following options

CLI default client Region [None]: eu-west-1
CLI default output format [None]: json
CLI profile name [AdministratorAccess-xxxx]: admin-prod-sso

This will then create the profile for the production platform
EOF

read -p "Press enter to continue"

aws configure sso

cat << EOF
Enter the following for the 3rd region

SSO session name (Recommended): dev 

you will then be shown a list of aws accounts to select. You can only select 1 option. You will be asked to supply some default configuration for the aws cli:

The third to select is analytical-platform-data-production

Then fill in the following options

CLI default client Region [None]: eu-west-1
CLI default output format [None]: json
CLI profile name [AdministratorAccess-xxxx]: admin-data-sso

This will then create the profile for the data production platform
EOF

read -p "Press enter to continue"

aws configure sso

aws-vault exec admin-dev-sso  -- aws eks --region eu-west-1 update-kubeconfig --name development-aWrhyc0m --alias dev-eks-cluster
aws-vault exec admin-prod-sso  -- aws eks --region eu-west-1 update-kubeconfig --name production-dBSvju9Y --alias prod-eks-cluster
kubectl config use-context dev-eks-cluster

# create virtual environment for python
python -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
pip3 install -r requirements.dev.txt
pre-commit install --hook-type commit-msg
pre-commit install

# add helm repo
helm repo add mojanalytics http://moj-analytics-helm-repo.s3-website-eu-west-1.amazonaws.com
helm repo update

# install npm packages
npm install
mkdir static
cp -R node_modules/accessible-autocomplete/dist/ static/accessible-autocomplete
cp -R node_modules/govuk-frontend/ static/govuk-frontend
cp -R node_modules/@ministryofjustice/frontend/ static/ministryofjustice-frontend
cp -R node_modules/html5shiv/dist/ static/html5-shiv
cp -R node_modules/jquery/dist/ static/jquery
cp -R node_modules/jquery-ui/dist/ static/jquery-ui
./node_modules/.bin/babel \
  controlpanel/frontend/static/module-loader.js \
  controlpanel/frontend/static/components \
  controlpanel/frontend/static/javascripts \
  -o static/app.js -s
./node_modules/.bin/sass --load-path=node_modules/ --style=compressed controlpanel/frontend/static/app.scss:static/app.css

python3 manage.py collectstatic

# create database and user
createuser -d controlpanel
createdb -U controlpanel controlpanel

# set env vars for db
export DB_USER=controlpanel
export DB_PASSWORD=password

python3 manage.py migrate
