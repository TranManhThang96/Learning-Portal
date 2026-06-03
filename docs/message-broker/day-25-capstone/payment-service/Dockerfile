FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY shared ./shared
COPY payment-service ./payment-service
RUN go build -o /out/service ./payment-service

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=build /out/service /service
ENTRYPOINT ["/service"]
