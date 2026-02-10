cmake_minimum_required(VERSION 3.10)
project(legs-main VERSION 1.0)


find_package(Threads REQUIRED)

add_executable(legs-main main.cpp)
target_link_libraries(legs-main Threads::Threads)

install(TARGETS legs-main DESTINATION bin)
