cmake_minimum_required(VERSION 3.10)
project(legs_main VERSION 1.0)

add_executable(legs_main main.cpp)

install(TARGETS legs_main DESTINATION bin)
