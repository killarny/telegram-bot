Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/vivid64"
  config.vm.synced_folder ".", "/telegram-bot"
  config.vm.provision "docker"
  config.vm.provision "shell", inline: <<-SHELL
    docker build -t telegram-bot /telegram-bot
    docker create --name telegram-bot telegram-bot
    docker start telegram-bot
  SHELL
end
