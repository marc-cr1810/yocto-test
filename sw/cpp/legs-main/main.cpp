#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <thread>
#include <unistd.h>

#define PPS_DEVICE "/dev/pps_interrupt"

void pps_monitor() {
  std::cout << "PPS Monitor Thread Started" << std::endl;

  int fd = open(PPS_DEVICE, O_RDONLY);
  if (fd < 0) {
    std::cerr << "Failed to open " << PPS_DEVICE << ": " << strerror(errno)
              << std::endl;
    return;
  }

  char buffer[32];
  while (true) {
    int ret = read(fd, buffer, sizeof(buffer) - 1);
    if (ret > 0) {
      buffer[ret] = '\0';
      // Remove newline if present
      if (buffer[ret - 1] == '\n')
        buffer[ret - 1] = '\0';
      std::cout << "[PPS] Interrupt Triggered! Count: " << buffer << std::endl;
    } else if (ret < 0) {
      std::cerr << "Error reading PPS: " << strerror(errno) << std::endl;
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
  }

  close(fd);
}

int main() {
  std::cout << "Hello from legs-main!" << std::endl;

  std::thread monitor(pps_monitor);
  monitor.detach();

  // Main loop
  while (true) {
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }

  return 0;
}
