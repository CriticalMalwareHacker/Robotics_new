/*
 * ParkSensei serial-drive firmware for Arduino Uno + Adafruit Motor Shield V1.
 * Four motors are grouped by side: M1+M3 left, M2+M4 right.
 *
 * Serial protocol at 115200 baud, one ASCII command per line:
 *   PING                         -> PONG
 *   MOVE <F|B|L|R> <pwm> <ms>   -> OK MOVE
 *   STOP                         -> OK STOP
 *   ESTOP                        -> OK ESTOP (latched until CLEAR)
 *   CLEAR                        -> OK CLEAR
 *   STATUS                       -> STATUS IDLE|MOVING|ESTOP
 *
 * Motor power must come from the motor supply/shield, not USB. A MOVE is a
 * short lease; it stops automatically after at most 500 ms unless renewed.
 */

#include <AFMotor.h>
#include <stdio.h>
#include <string.h>

AF_DCMotor motor1(1);
AF_DCMotor motor2(2);
AF_DCMotor motor3(3);
AF_DCMotor motor4(4);

// Physical side mapping for a four-wheel skid-steer chassis.
AF_DCMotor *const LEFT_FRONT_MOTOR = &motor1;
AF_DCMotor *const RIGHT_FRONT_MOTOR = &motor2;
AF_DCMotor *const LEFT_REAR_MOTOR = &motor3;
AF_DCMotor *const RIGHT_REAR_MOTOR = &motor4;

// Keep the lease close to the backend's short refresh interval: if serial
// commands stop arriving, full-power movement ends within 220 ms by default.
const unsigned long MIN_MOVE_MS = 100;
const unsigned long MAX_MOVE_MS = 500;
// All four channels were confirmed to start at full PWM in the V1 diagnostic.
// Use that proven level for manual movement so loaded rear motors start too.
const int MIN_DRIVE_PWM = 255;
const size_t LINE_CAPACITY = 48;

char lineBuffer[LINE_CAPACITY];
size_t lineLength = 0;
bool estopLatched = false;
bool moving = false;
unsigned long stopAt = 0;

void stopMotors()
{
  motor1.run(RELEASE);
  motor2.run(RELEASE);
  motor3.run(RELEASE);
  motor4.run(RELEASE);
  moving = false;
}

void setAllSpeeds(int speed)
{
  motor1.setSpeed(speed);
  motor2.setSpeed(speed);
  motor3.setSpeed(speed);
  motor4.setSpeed(speed);
}

void driveLeftSide(uint8_t direction)
{
  LEFT_FRONT_MOTOR->run(direction);
  LEFT_REAR_MOTOR->run(direction);
}

void driveRightSide(uint8_t direction)
{
  RIGHT_FRONT_MOTOR->run(direction);
  RIGHT_REAR_MOTOR->run(direction);
}

void beginMove(char direction, int speed, unsigned long durationMs)
{
  if (estopLatched)
  {
    Serial.println("ERR ESTOP");
    return;
  }

  speed = constrain(speed, 0, 255);
  if (speed == 0)
  {
    stopMotors();
    Serial.println("OK STOP");
    return;
  }

  // The app's default PWM is 120; raise nonzero commands to the known-working
  // diagnostic level so all four loaded motors start.
  if (speed < MIN_DRIVE_PWM)
    speed = MIN_DRIVE_PWM;

  durationMs = constrain(durationMs, MIN_MOVE_MS, MAX_MOVE_MS);
  setAllSpeeds(speed);

  switch (direction)
  {
  case 'F':
    driveLeftSide(FORWARD);
    driveRightSide(FORWARD);
    break;
  case 'B':
    driveLeftSide(BACKWARD);
    driveRightSide(BACKWARD);
    break;
  case 'L':
    // Counter-rotate both sides so all four motors contribute to the turn.
    driveLeftSide(BACKWARD);
    driveRightSide(FORWARD);
    break;
  case 'R':
    // Counter-rotate both sides so all four motors contribute to the turn.
    driveLeftSide(FORWARD);
    driveRightSide(BACKWARD);
    break;
  default:
    stopMotors();
    Serial.println("ERR DIRECTION");
    return;
  }

  moving = true;
  stopAt = millis() + durationMs;
  Serial.println("OK MOVE");
}

void handleLine(char *line)
{
  if (strcmp(line, "PING") == 0)
  {
    Serial.println("PONG");
    return;
  }

  if (strcmp(line, "STOP") == 0)
  {
    stopMotors();
    Serial.println("OK STOP");
    return;
  }

  if (strcmp(line, "ESTOP") == 0)
  {
    estopLatched = true;
    stopMotors();
    Serial.println("OK ESTOP");
    return;
  }

  if (strcmp(line, "CLEAR") == 0)
  {
    stopMotors();
    estopLatched = false;
    Serial.println("OK CLEAR");
    return;
  }

  if (strcmp(line, "STATUS") == 0)
  {
    if (estopLatched)
      Serial.println("STATUS ESTOP");
    else if (moving)
      Serial.println("STATUS MOVING");
    else
      Serial.println("STATUS IDLE");
    return;
  }

  char direction = 0;
  int speed = 0;
  unsigned long durationMs = 0;
  if (sscanf(line, "MOVE %c %d %lu", &direction, &speed, &durationMs) == 3)
  {
    beginMove(direction, speed, durationMs);
    return;
  }

  Serial.println("ERR COMMAND");
}

void setup()
{
  Serial.begin(115200);
  stopMotors();
  Serial.println("READY");
}

void loop()
{
  while (Serial.available() > 0)
  {
    const char c = (char)Serial.read();
    if (c == '\r')
      continue;

    if (c == '\n')
    {
      lineBuffer[lineLength] = '\0';
      if (lineLength > 0)
        handleLine(lineBuffer);
      lineLength = 0;
    }
    else if (lineLength < LINE_CAPACITY - 1)
    {
      lineBuffer[lineLength++] = c;
    }
    else
    {
      lineLength = 0;
      stopMotors();
      Serial.println("ERR LINE_TOO_LONG");
    }
  }

  const unsigned long now = millis();
  if (moving && (long)(now - stopAt) >= 0)
    stopMotors();
}
