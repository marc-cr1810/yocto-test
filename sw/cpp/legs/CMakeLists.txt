cmake_minimum_required(VERSION 3.10)
project(legs VERSION 1.0)

add_executable(legs main.cpp)

install(TARGETS legs DESTINATION bin)
