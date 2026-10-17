'use client'

import { ChakraProvider } from '@chakra-ui/react'
import { system } from './theme.mjs'

import { SessionProvider } from "../SessionProvider";
import { Toaster } from "./toaster";

export function Provider(props) {
  return (
    <ChakraProvider value={system}>
      <SessionProvider>{props.children}<Toaster /></SessionProvider>
    </ChakraProvider>
  )
}
