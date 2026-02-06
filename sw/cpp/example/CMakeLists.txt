cmake_minimum_required(VERSION 3.10)
project(example VERSION 1.0)

find_package(spdlog REQUIRED)

add_executable(example main.cpp)

target_link_libraries(example PRIVATE spdlog::spdlog)

install(TARGETS example DESTINATION bin)
